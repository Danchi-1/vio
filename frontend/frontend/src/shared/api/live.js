import { request } from './client.js';
import { ApiError } from './errors.js';

// Source: VIO_HACKATHON_SPECIFICATION.md section 8, as directed by the project owner.
// Anything the spec does not define is listed in UNRESOLVED and throws 'unsupported'.
const notInSpec = () => Promise.reject(new ApiError('unsupported'));

export const UNRESOLVED = [
  'sign-out', 'universities and catalogue (faculties, departments, courses list)', 'academic session',
  'report options (categories, date bounds, limits)', 'list own reports', 'findings list and detail',
  'timetable upload', 'lecturer private-link redemption', 'dashboard response shape (ASSUMED in dashboardContract.js)', 'track-report response shape',
];

export const liveService = {
  // student auth and setup
  requestOtp: (email) => request('POST', '/student/auth/request-otp', { body: { email } }),
  verifyOtp: (email, code) => request('POST', '/student/auth/verify-otp', { body: { email, code } }),
  getProfile: () => request('GET', '/student/profile'),
  updateProfile: (p) => request('PUT', '/student/profile', { body: p }), // { level, department_id }
  getCourses: () => request('GET', '/student/courses'),
  updateCourses: (course_ids) => request('PUT', '/student/courses', { body: { course_ids } }),
  // reports
  createReport: (r) => request('POST', '/reports', { body: r }), // { course_id, category, incident_date, description }
  trackReport: (code) => request('GET', `/reports/track/${encodeURIComponent(code)}`),
  confirmFinding: (id, comment) => request('POST', `/findings/${encodeURIComponent(id)}/confirm`, { body: { comment } }),
  // lecturer
  postClassNotice: (n) => request('POST', '/lecturer/class-notices', { body: n, bearer: true }),
  postLecturerReply: (r) => request('POST', '/lecturer/replies', { body: r, bearer: true }),
  // authority
  redeemAuthorityLink: (token) => request('POST', '/authority/access', { body: { token } }),
  getDelivery: (id) => request('GET', `/authority/deliveries/${encodeURIComponent(id)}`, { bearer: true }),
  acknowledgeDelivery: (id) => request('POST', `/authority/deliveries/${encodeURIComponent(id)}/acknowledgement`, { bearer: true }),
  respondToDelivery: (id, b) => request('POST', `/authority/deliveries/${encodeURIComponent(id)}/responses`, { body: b, bearer: true }),
  appealDelivery: (id, body) => request('POST', `/authority/deliveries/${encodeURIComponent(id)}/appeals`, { body: { body }, bearer: true }),
  // public
  getDashboard: (q, signal) => request('GET', '/dashboard/overview', { query: q, signal }), // { department_id, month }

  signOut: notInSpec, getUniversities: notInSpec, getReportOptions: notInSpec,
  listReports: notInSpec, listFindings: notInSpec, uploadTimetable: notInSpec, redeemLecturerLink: notInSpec,
};
