// Dark device mockup. Everything on it is labelled as a sample; there is no real report or data.
export default function DeviceMock() {
  return (
    <div className="device-stage" role="group" aria-label="Sample of the VIO interface. Illustrative only.">
      <div className="device">
        <div className="device-bar"><span>VIO · Track a report</span><span className="tag">Sample screen, no real report</span></div>
        <div className="panel">
          <h3>Report received</h3>
          <div className="minis">
            <div className="mini"><small>Course</small><b>Sample code</b></div>
            <div className="mini"><small>Incident date</small><b>Sample date</b></div>
            <div className="mini"><small>Status</small><b>Collecting</b></div>
          </div>
          <div className="sketch">
            <div className="bars" aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /></div>
            <p>Public dashboard layout sketch. No data.</p>
          </div>
        </div>
      </div>
      <div className="float-card"><small>Finding statuses</small><b>6</b></div>
    </div>
  );
}
