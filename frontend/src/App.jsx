import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import PublicShell from './shells/PublicShell.jsx';
import StudentShell from './shells/StudentShell.jsx';
import SecureShell from './shells/SecureShell.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import GuidelinesPage from './pages/GuidelinesPage.jsx';
import HomePage from './pages/HomePage.jsx';
import NotFoundPage from './pages/NotFoundPage.jsx';
import SetupPage from './pages/SetupPage.jsx';
import SignInPage from './pages/SignInPage.jsx';
import SignUpPage from './pages/auth/SignUpPage.jsx';
import {
  FindingDetailPage,
  FindingsListPage,
  NewReportPage,
  StudentHomePage,
  TrackReportPage,
} from './pages/StudentPages.jsx';
import {
  AccessExpiredPage,
  AuthorityAccessPage,
  AuthorityDeliveryPage,
  LecturerAccessPage,
  LecturerFindingPage,
  LecturerNoticesPage,
} from './pages/SecurePages.jsx';

const router = createBrowserRouter([
  { path: '/sign-up', element: <SignUpPage /> },
  {
    element: <PublicShell />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/dashboard', element: <DashboardPage /> },
      { path: '/sign-in', element: <SignInPage /> },
      { path: '/sign-in/verify', element: <SignInPage /> },
      { path: '/guidelines', element: <GuidelinesPage /> },
      { path: '/track', element: <TrackReportPage /> },
      { path: '/track/:trackingCode', element: <TrackReportPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
  {
    element: <StudentShell />,
    children: [
      { path: '/setup', element: <SetupPage section="profile" /> },
      { path: '/setup/courses', element: <SetupPage section="courses" /> },
      { path: '/setup/timetable', element: <SetupPage section="timetable" /> },
      { path: '/student', element: <StudentHomePage /> },
      { path: '/student/reports/new', element: <NewReportPage /> },
      { path: '/student/reports/:trackingCode', element: <TrackReportPage /> },
      { path: '/student/findings', element: <FindingsListPage /> },
      { path: '/student/findings/:findingId', element: <FindingDetailPage /> },
    ],
  },
  {
    element: <SecureShell />,
    children: [
      { path: '/lecturer/access', element: <LecturerAccessPage /> },
      { path: '/lecturer/findings/:findingId', element: <LecturerFindingPage /> },
      { path: '/lecturer/notices', element: <LecturerNoticesPage /> },
      { path: '/authority/access', element: <AuthorityAccessPage /> },
      { path: '/authority/deliveries/:deliveryId', element: <AuthorityDeliveryPage /> },
      { path: '/access-expired', element: <AccessExpiredPage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
