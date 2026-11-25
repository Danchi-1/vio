// Copy from the onboarding page. Every sample is labelled; no invented counts, testimonials or logos.
export const PHRASES = ['deserves to be heard.', 'deserves to be listened to.', 'deserves a fair hearing.', 'deserves to be understood.'];

export const STATS = [
  { value: '4', title: 'Steps', text: 'Sign-in to tracking' },
  { value: '6', title: 'Finding statuses', text: 'Labelled by the system' },
  { value: '20', title: 'Minimum group', text: 'Smaller groups hidden' },
  { value: '1', title: 'Report', text: 'A claim, not a finding' },
];

export const STEPS = [
  { n: '01', title: 'Verify', text: 'Choose your university, enter your school email and confirm the one-time code.', to: '/sign-in', label: 'Go to student sign in' },
  { n: '02', title: 'Set up', text: 'Confirm faculty, department, level and session, then add the courses you take. The course list is declared by you.', to: '/setup', label: 'Go to setup' },
  { n: '03', title: 'Report the facts', text: 'Pick the course and date, describe what happened in up to 2,000 characters and review before you submit.', to: '/student/reports/new', label: 'Go to file a report' },
  { n: '04', title: 'Track it', text: 'Save the tracking code shown once. Follow the status and explanation from your own account.', to: '/student', label: 'Go to your student home' },
  { n: '05', title: 'Right of reply', text: 'Lecturers and authorities get private, time-limited links to an anonymised summary and can reply where the system permits.', to: '/lecturer/access', label: 'Go to private link access' },
  { n: '06', title: 'Public dashboard', text: 'Published aggregate counts only. No report text, names, IDs or tracking codes.', to: '/dashboard', label: 'Go to the public dashboard' },
];

export const FAIR = [
  { title: 'Your email', text: 'Your school email is used to verify you. It is not shown on reports or on the public dashboard.' },
  { title: 'Claims and findings', text: 'A report is a claim. A finding is a separate thing, and a published result is another. One report does not become public on its own.' },
  { title: 'Right of reply', text: 'Lecturers and school authorities see only what the system allows, such as an anonymised summary, and can reply or appeal where the system permits it.' },
  { title: 'What the public sees', text: 'Published aggregate counts only. Groups of fewer than 20 students are hidden.' },
];

export const STATUSES = [
  { key: 'collecting', label: 'Collecting', text: 'Report received. It is not yet a finding.' },
  { key: 'held', label: 'Held', text: 'Not public.' },
  { key: 'cleared', label: 'Cleared', text: 'Passed checks. Not necessarily public.' },
  { key: 'published', label: 'Published', text: 'The only status that counts toward the public dashboard.' },
  { key: 'rejected', label: 'Rejected', text: 'The system shows a safe explanation.' },
  { key: 'disputed', label: 'Disputed', text: 'Not public. No new deliveries.' },
];

export const FAQ = [
  { q: 'Is my school email shown anywhere?', a: 'No. Your email is used to confirm you are a student. It does not appear on your report or on the public dashboard.', pending: 'Final wording on email handling is waiting for sign-off from the backend team.' },
  { q: 'Can I name my lecturer?', a: "The report form has no field for a lecturer's name. Describe what happened and leave out names and personal details." },
  { q: 'What happens after I submit?', a: 'You get a tracking code once. The system assesses reports for patterns. Your report is treated as a claim until the system establishes a finding, and you can follow its status from your account.' },
  { q: 'Who can see my report?', a: 'You can, from your own account. Lecturers and school authorities receive only what the system permits, such as an anonymised summary. The public sees published aggregate counts only.' },
  { q: 'Is VIO completely anonymous?', a: 'No system can promise that. VIO keeps your email off reports and the public dashboard, but details you write can still identify someone. Keep descriptions factual and free of names.' },
];
