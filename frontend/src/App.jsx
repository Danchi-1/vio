import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import PublicShell from './shells/PublicShell.jsx';
import StudentShell from './shells/StudentShell.jsx';
import SecureShell from './shells/SecureShell.jsx';
import ComingSoon from './shared/components/ComingSoon.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import HomePage from './pages/HomePage.jsx';
import NotFoundPage from './pages/NotFoundPage.jsx';
import LecturerAccessPage from './pages/lecturer/LecturerAccessPage.jsx';
import LecturerFindingPage from './pages/lecturer/LecturerFindingPage.jsx';
import LecturerNoticesPage from './pages/lecturer/LecturerNoticesPage.jsx';
import SignUpPage from './pages/auth/SignUpPage.jsx';

const soon = (title, note) => <ComingSoon title={title} note={note} />;

const router = createBrowserRouter([
  { path: '/sign-up', element: <SignUpPage /> },
  {
    element: <PublicShell />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/dashboard', element: <DashboardPage /> },
      { path: '/sign-in', element: soon('Student sign in') },
      { path: '/sign-in/verify', element: soon('Verify your code') },
      { path: '/guidelines', element: soon('Reporting guidelines') },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
  {
    element: <StudentShell />,
    children: [
      { path: '/setup', element: soon('Set up your profile') },
      { path: '/setup/courses', element: soon('Register your courses') },
      { path: '/setup/timetable', element: soon('Upload your timetable', 'Not in the API spec yet.') },
      { path: '/student', element: soon('My reports') },
      { path: '/student/reports/new', element: soon('File a report') },
      { path: '/student/reports/:trackingCode', element: soon('Track a report') },
      { path: '/student/findings', element: soon('Findings') },
      { path: '/student/findings/:findingId', element: soon('Finding') },
    ],
  },
  {
    element: <SecureShell />,
    children: [
      { path: '/lecturer/access', element: <LecturerAccessPage /> },
      { path: '/lecturer/findings/:findingId', element: <LecturerFindingPage /> },
      { path: '/lecturer/notices', element: <LecturerNoticesPage /> },
      { path: '/authority/access', element: soon('Authority access') },
      { path: '/authority/deliveries/:deliveryId', element: soon('Delivery') },
      { path: '/access-expired', element: soon('This link cannot be used') },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
