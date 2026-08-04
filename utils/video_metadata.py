import logging
import re
import struct
from pathlib import Path

logger = logging.getLogger(__name__)

_MAX_SCAN_BYTES = 64 * 1024 * 1024
_MKV_CHUNK_BYTES = 32 * 1024 * 1024

_DEFAULT_CAMERA_PREFIXES = (
    "cam", "camera", "ch", "channel", "ip", "ipc", "dvr", "nvr", "cctv",
)
_DEFAULT_LOCATION_KEYWORDS = (
    "area", "plant", "line", "zone", "floor", "building", "gate", "dock",
    "entrance", "exit", "hall", "sector", "warehouse", "production",
    "assembly", "loading", "parking", "section", "bay", "yard", "room",
    "block", "storage", "workshop", "lot", "office", "unit", "level", "site",
    "campus", "factory", "stage", "station",
    "north", "south", "east", "west", "main", "rear", "front", "side",
    "upper", "lower", "middle", "back", "central",
)
_DEFAULT_NOISE_TOKENS = (
    "rec", "record", "recording", "video", "clip", "sample", "test",
    "final", "new", "copy", "export", "output", "tmp", "h264", "h265",
    "mpeg", "full", "raw",
)

_MP4_KEY_MAP = {
    "nam": "title", "titl": "title", "name": "title", "tite": "title",
    "mak": "make", "mod": "model",
    "cmt": "comment", "des": "comment", "cdes": "comment",
    "loci": "location",
}


def _decode_text(data):
    if data is None:
        return ""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return data.decode("utf-16").strip(" \x00")
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8", "latin-1"):
        try:
            return data.decode(enc).strip(" \x00")
        except (UnicodeDecodeError, ValueError):
            continue
    return ""


def _clean(value):
    if not value:
        return None
    value = "".join(ch for ch in value if ch.isprintable())
    value = value.strip()
    return value or None


def _iter_boxes(data, start=0, end=None):
    if end is None:
        end = len(data)
    i = start
    while i + 8 <= end:
        size = struct.unpack(">I", data[i:i + 4])[0]
        box_type = data[i + 4:i + 8]
        header_len = 8
        if size == 1:
            if i + 16 > end:
                break
            size = struct.unpack(">Q", data[i + 8:i + 16])[0]
            header_len = 16
        elif size == 0:
            size = end - i
        if size < header_len:
            i += 4
            continue
        box_end = i + size
        if box_end > end:
            break
        yield box_type, data[i + header_len:box_end]
        i = box_end


def _read_box_from_stream(fh, box_type, budget=_MAX_SCAN_BYTES):
    while fh.tell() < budget:
        header = fh.read(8)
        if len(header) < 8:
            return None
        size, btype = struct.unpack(">I4s", header)
        header_len = 8
        if size == 1:
            ext = fh.read(8)
            if len(ext) < 8:
                return None
            size = struct.unpack(">Q", ext)[0]
            header_len = 16
        elif size == 0:
            return fh.read()
        if size < header_len:
            return None
        if btype == box_type:
            payload_len = size - header_len
            return fh.read(payload_len) if payload_len else b""
        fh.seek(size - header_len, 1)
    return None


def _parse_loci(payload):
    if len(payload) < 7:
        return None
    body = payload[6:]
    if not body:
        return None
    n = body[0]
    if n and n < len(body):
        text = _decode_text(body[1:1 + n])
        if _clean(text):
            return text
    end = body.find(b"\x00")
    if end >= 0:
        return _clean(_decode_text(body[:end]))
    return _clean(_decode_text(body))


def _extract_ilst_value(item_payload):
    for t, p in _iter_boxes(item_payload):
        if t == b"data" and len(p) >= 8:
            return _clean(_decode_text(p[8:]))
    return None


def _parse_mp4(path):
    raw = {}
    with open(path, "rb") as fh:
        moov = _read_box_from_stream(fh, b"moov")
    if not moov:
        return raw

    for _, udta in _iter_boxes(moov):
        for btype, payload in _iter_boxes(udta):
            if btype == b"meta" and len(payload) > 4:
                for t, p in _iter_boxes(payload[4:]):
                    if t == b"ilst":
                        for item_type, item_payload in _iter_boxes(p):
                            key = item_type.decode("latin-1").replace("\xa9", "").lower()
                            value = _extract_ilst_value(item_payload)
                            if value and key in _MP4_KEY_MAP:
                                raw[_MP4_KEY_MAP[key]] = value
            elif btype == b"loci":
                loc = _parse_loci(payload)
                if loc:
                    raw["location"] = loc

    for btype, payload in _iter_boxes(moov):
        if btype == b"loci":
            loc = _parse_loci(payload)
            if loc:
                raw["location"] = loc

    return raw


def _parse_avi(path):
    raw = {}
    with open(path, "rb") as fh:
        if fh.read(4) != b"RIFF":
            return raw
        header = fh.read(4)
        if len(header) < 4:
            return raw
        total = struct.unpack("<I", header)[0]
        if fh.read(4) != b"AVI ":
            return raw
        end = min(fh.tell() + total, _MAX_SCAN_BYTES)
        while fh.tell() + 8 <= end:
            cid = fh.read(4)
            csize_bytes = fh.read(4)
            if len(csize_bytes) < 4:
                break
            csize = struct.unpack("<I", csize_bytes)[0]
            payload = fh.read(csize)
            if len(payload) < csize:
                break
            if cid == b"LIST" and payload[:4] == b"INFO":
                avi_map = {
                    "INAM": "title", "IART": "make", "IMOD": "model",
                    "IMDL": "model", "ILOC": "location", "ICMT": "comment",
                }
                j = 4
                while j + 8 <= len(payload):
                    scid = payload[j:j + 4]
                    ssize = struct.unpack("<I", payload[j + 4:j + 8])[0]
                    spayload = payload[j + 8:j + 8 + ssize]
                    key = avi_map.get(scid.decode("latin-1"))
                    if key:
                        raw[key] = _clean(_decode_text(spayload))
                    j += 8 + ssize + (ssize % 2)
            if csize % 2:
                fh.seek(1, 1)
            if fh.tell() > end:
                break
    return raw


def _mkv_collect_strings(buf, element_id):
    results = []
    start = 0
    while True:
        idx = buf.find(element_id, start)
        if idx < 0:
            break
        pos = idx + len(element_id)
        if pos >= len(buf):
            break
        first = buf[pos]
        size_len = 1
        while first & (0x80 >> (size_len - 1)) == 0:
            size_len += 1
            if pos + size_len >= len(buf):
                break
        if pos + size_len > len(buf):
            break
        size = int.from_bytes(buf[pos:pos + size_len], "big")
        size &= (1 << (8 * size_len - size_len)) - 1
        data = buf[pos + size_len:pos + size_len + size]
        if len(data) < size:
            break
        text = _clean(_decode_text(data))
        if text:
            results.append(text)
        start = idx + len(element_id)
    return results


def _read_head_tail(path):
    size = path.stat().st_size
    with open(path, "rb") as fh:
        head = fh.read(_MKV_CHUNK_BYTES)
        if size > _MKV_CHUNK_BYTES:
            fh.seek(size - _MKV_CHUNK_BYTES)
            tail = fh.read(_MKV_CHUNK_BYTES)
            return head + tail
        return head


def _parse_mkv(path):
    raw = {}
    buf = _read_head_tail(path)
    titles = _mkv_collect_strings(buf, b"\x7b\xa9")
    tag_names = _mkv_collect_strings(buf, b"\x45\xa3")
    tag_strings = _mkv_collect_strings(buf, b"\x44\x87")
    if titles:
        raw["title"] = titles[0]
    for name, value in zip(tag_names, tag_strings):
        raw[name.upper().strip()] = value
    return raw


_GENERIC_COMMENT_TOKENS = (
    "record", "copyright", "dvr", "encoded", "software", "firmware",
    "made with", "created by", "generated", "encoder", "www.",
)


def _is_generic_comment(comment):
    lowered = comment.lower()
    return any(token in lowered for token in _GENERIC_COMMENT_TOKENS)


def _map_to_camera(raw):
    result = {}
    make = _clean(raw.get("make"))
    model = _clean(raw.get("model"))
    title = _clean(raw.get("title"))
    location = _clean(raw.get("location"))

    for key, value in raw.items():
        key_upper = str(key).upper()
        if key_upper in ("LOCATION", "RECORDING_LOCATION", "SUB_LOCATION"):
            location = location or _clean(value)
        elif key_upper in ("CAMERA_ID", "CAMERA_MODEL", "MODEL"):
            model = model or _clean(value)
        elif key_upper == "CAMERA_MAKE":
            make = make or _clean(value)
        elif key_upper in ("CAMERA_NAME", "CAMERA_TITLE"):
            title = title or _clean(value)

    if model:
        result["camera_id"] = model
    elif make:
        result["camera_id"] = make

    name = title
    if not name:
        name = " ".join(x for x in (make, model) if x) or None
    if name:
        result["camera_name"] = name

    if not location:
        comment = _clean(raw.get("comment"))
        if comment and not _is_generic_comment(comment):
            location = comment

    if location:
        result["location"] = location

    return result


def _is_camera_token(token, prefixes):
    t = token.lower()
    if re.fullmatch(r"(?:cam|camera|ch|channel|ip|ipc|dvr|nvr|cctv)[-_]?\d{1,4}", t):
        return True
    if t in prefixes:
        return True
    if "cam" in t:
        return True
    return False


def _is_datetime_token(token):
    t = token.lower()
    if re.fullmatch(r"\d{6,16}", t):
        return True
    if re.fullmatch(r"\d{4}[-_]\d{2}[-_]\d{2}", t):
        return True
    if re.fullmatch(r"\d{1,2}[-_]\d{1,2}[-_]\d{2,4}", t):
        return True
    if re.fullmatch(r"\d{2}:\d{2}:\d{2}", t):
        return True
    return False


def _is_resolution_token(token):
    t = token.lower()
    return bool(
        re.fullmatch(r"\d{3,5}x\d{3,5}", t)
        or re.fullmatch(r"\d{3,4}p", t)
        or re.fullmatch(r"\d{1,2}k", t)
    )


def _has_location_keyword(token, keywords):
    t = token.lower()
    return any(k in t for k in keywords)


def _cfg_value(config, key, default):
    if config is None:
        return default
    if hasattr(config, key):
        return getattr(config, key)
    if isinstance(config, dict):
        return config.get(key, default)
    return default


def parse_filename_metadata(video_path, config=None):
    prefixes = tuple(_cfg_value(config, "CAMERA_PREFIXES", _DEFAULT_CAMERA_PREFIXES))
    keywords = tuple(_cfg_value(config, "LOCATION_KEYWORDS", _DEFAULT_LOCATION_KEYWORDS))
    noise = tuple(_cfg_value(config, "NOISE_TOKENS", _DEFAULT_NOISE_TOKENS))

    stem = Path(video_path).stem
    tokens = [t for t in re.split(r"[_\-\s.()\[\]]+", stem) if t]

    merged = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.lower() in prefixes and i + 1 < len(tokens) and tokens[i + 1].isdigit():
            merged.append(f"{tok}_{tokens[i + 1]}")
            i += 2
            continue
        merged.append(tok)
        i += 1
    tokens = merged

    camera_tokens = []
    numeric = []
    descriptive = []
    for tok in tokens:
        if _is_camera_token(tok, prefixes):
            camera_tokens.append(tok)
        elif _is_datetime_token(tok):
            continue
        elif _is_resolution_token(tok):
            continue
        elif tok.lower() in noise:
            continue
        elif tok.isdigit() and len(tok) <= 4:
            numeric.append(tok)
        else:
            descriptive.append(tok)

    result = {}
    if camera_tokens:
        result["camera_id"] = camera_tokens[0]
    elif numeric:
        result["camera_id"] = numeric[0]

    loc_tokens = [
        t for t in descriptive
        if len(t) == 1 or _has_location_keyword(t, keywords)
    ]
    name_tokens = [t for t in descriptive if t not in loc_tokens]

    if loc_tokens:
        result["location"] = " ".join(loc_tokens)
    elif descriptive and "camera_id" not in result:
        result["location"] = " ".join(descriptive)

    result["camera_name"] = " ".join(name_tokens) or result.get("camera_id")
    if not descriptive and not camera_tokens and not numeric:
        result.pop("camera_name", None)

    if result:
        logger.info(f"Parsed camera info from filename {Path(video_path).name}: {result}")
    return result


def extract_video_metadata(video_path, config=None):
    path = Path(video_path)
    if not path.exists():
        return {}
    ext = path.suffix.lower()
    raw = {}
    try:
        if ext in (".mp4", ".mov", ".m4v"):
            raw = _parse_mp4(path)
        elif ext == ".avi":
            raw = _parse_avi(path)
        elif ext in (".mkv", ".webm"):
            raw = _parse_mkv(path)
    except Exception as e:
        logger.warning(f"Metadata extraction failed for {path.name}: {e}")

    info = _map_to_camera(raw)
    if _cfg_value(config, "FILENAME_PARSING_ENABLED", True):
        filename_info = parse_filename_metadata(video_path, config)
        for key in ("camera_name", "camera_id", "location"):
            if not info.get(key) and filename_info.get(key):
                info[key] = filename_info[key]

    if info:
        logger.info(f"Camera info for {path.name}: {info}")
    return info
