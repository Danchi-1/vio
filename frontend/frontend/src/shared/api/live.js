import { request } from './client.js';
import { ApiError } from './errors.js';

export const UNRESOLVED = ['timetable upload (uses course registration)'];

export const liveService = {
  // student auth and setup
  requestOtp: (email) => request('POST', '/student/auth/request-otp', { body: { email } }),
  verifyOtp: (email, code) => request('POST', '/student/auth/verify-otp', { body: { email, code } }),
  getSession: () => request('GET', '/auth/session'),
  signOut: () => request('DELETE', '/auth/session'),
  getProfile: () => request('GET', '/student/profile'),
  updateProfile: (p) => request('PUT', '/student/profile', { body: p }),
  confirmSession: (academic_session) => request('POST', '/student/profile/confirm-session', { body: { academic_session } }),
  getCourses: () => request('GET', '/student/courses'),
  updateCourses: (course_ids, academic_session) =>
    request('PUT', '/student/courses', { body: academic_session ? { course_ids, academic_session } : { course_ids } }),

  // public catalogue
  getUniversities: () => request('GET', '/universities'),
  getCatalogue: (shortName = 'FUNAAB') => request('GET', `/universities/${encodeURIComponent(shortName)}/catalogue`),
  getAcademicSessions: () => request('GET', '/academic-sessions'),

  // reports & findings
  getReportOptions: () => request('GET', '/student/report-options'),
  createReport: (r) => request('POST', '/reports', { body: r }),
  listReports: () => request('GET', '/student/reports'),
  getStudentReport: (code) => request('GET', `/student/reports/${encodeURIComponent(code)}`),
  trackReport: (code) => request('GET', `/reports/track/${encodeURIComponent(code)}`),
  listFindings: () => request('GET', '/student/findings/confirmable'),
  getFinding: (id) => request('GET', `/student/findings/${encodeURIComponent(id)}`),
  confirmFinding: (id, comment) => request('POST', `/findings/${encodeURIComponent(id)}/confirm`, { body: { comment: comment || null } }),

  // lecturer
  obtainLecturerSession: (body) => request('POST', '/lecturer/session', { body }),
  postClassNotice: (n) => request('POST', '/lecturer/class-notices', { body: n, bearer: true }),
  postLecturerReply: (r) => request('POST', '/lecturer/replies', { body: r, bearer: true }),

  // authority
  redeemAuthorityLink: (token) => request('POST', '/authority/access', { body: { token } }),
  getDelivery: (id) => request('GET', `/authority/deliveries/${encodeURIComponent(id)}`, { bearer: true }),
  acknowledgeDelivery: (id) => request('POST', `/authority/deliveries/${encodeURIComponent(id)}/acknowledgement`, { bearer: true }),
  respondToDelivery: (id, b) => request('POST', `/authority/deliveries/${encodeURIComponent(id)}/responses`, { body: b, bearer: true }),
  appealDelivery: (id, body) => request('POST', `/authority/deliveries/${encodeURIComponent(id)}/appeals`, { body: { body }, bearer: true }),

  // public dashboard
  getDashboard: (q, signal) => request('GET', '/dashboard/overview', { query: q, signal }),

  uploadTimetable: () => Promise.reject(new ApiError('unsupported')),
  redeemLecturerLink: () => Promise.reject(new ApiError('unsupported')),
};
