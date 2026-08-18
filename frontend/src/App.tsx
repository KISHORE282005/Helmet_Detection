import { Link, Navigate, Route, Routes } from 'react-router-dom';
import { AppShell, PageHeader } from './components/layout/AppShell';
import { Button, EmptyState, Panel } from './components/ui/primitives';

import Dashboard from './pages/Dashboard';
import LiveCamerasPage, { CameraGridPage } from './pages/LiveCameras';
import ActiveViolations from './pages/ActiveViolations';
import IncidentHistory from './pages/IncidentHistory';
import IncidentDetail from './pages/IncidentDetail';
import Evidence from './pages/Evidence';
import VideoAnalysis from './pages/VideoAnalysis';
import Reports from './pages/Reports';
import Analytics from './pages/Analytics';
import NVAAnalysis from './pages/NVAAnalysis';
import CameraManagement from './pages/CameraManagement';
import AIModels from './pages/AIModels';
import Settings from './pages/Settings';

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/live" element={<LiveCamerasPage />} />
        <Route path="/grid" element={<CameraGridPage />} />
        <Route path="/analysis" element={<VideoAnalysis />} />

        <Route path="/violations" element={<ActiveViolations />} />
        <Route path="/incidents" element={<IncidentHistory />} />
        <Route path="/incidents/:incidentId" element={<IncidentDetail />} />
        <Route path="/evidence" element={<Evidence />} />

        <Route path="/reports" element={<Reports />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/nva" element={<NVAAnalysis />} />

        <Route path="/cameras" element={<CameraManagement />} />
        <Route path="/models" element={<AIModels />} />
        <Route path="/settings" element={<Settings />} />

        {/* Legacy path kept so bookmarks to the old grid still resolve. */}
        <Route path="/camera-grid" element={<Navigate to="/grid" replace />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </AppShell>
  );
}

function NotFound() {
  return (
    <>
      <PageHeader title="Page not found" />
      <Panel>
        <EmptyState
          title="That page does not exist"
          description="The link may be out of date. Return to the operations centre to continue."
          action={
            <Link to="/">
              <Button variant="primary" size="sm">
                Back to dashboard
              </Button>
            </Link>
          }
        />
      </Panel>
    </>
  );
}
