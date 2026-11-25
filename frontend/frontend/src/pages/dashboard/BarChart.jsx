import { useId } from 'react';

const plural = (n) => `${n} published finding${n === 1 ? '' : 's'}`;

export default function BarChart({ index, kicker, title, explain, period, items }) {
  const id = useId();
  const max = Math.max(...items.map((i) => i.count), 1);
  return (
    <section className="dash-sec reveal" aria-labelledby={id}>
      <div className="dash-sec__head">
        <span className="label">{String(index).padStart(2, '0')} · {kicker}</span>
        <h2 id={id} className="dash-h3">{title}</h2>
        <p className="small"><strong>Period:</strong> {period}. {explain}</p>
      </div>
      <ul className="dbars">
        {items.map((it) => (
          <li key={it.key}>
            {/* Focusable so the tooltip works by keyboard as well as hover. */}
            <button type="button" className="bar" aria-label={`${it.label}: ${plural(it.count)}`}>
              <span className="bar__label">{it.label}</span>
              <span className="bar__track" aria-hidden="true"><span className="bar__fill" style={{ width: `${(it.count / max) * 100}%` }} /></span>
              <span className="bar__value" aria-hidden="true">{it.count}</span>
              <span className="bar__tip" aria-hidden="true">{plural(it.count)} in {it.label}</span>
            </button>
          </li>
        ))}
      </ul>
      <details className="table-alt">
        <summary className="btn btn-outline btn-sm">View as table</summary>
        <div className="table-wrap">
          <table>
            <caption className="sr-only">{title}. {period}.</caption>
            <thead><tr><th scope="col">{kicker.replace(/^(By|Over) /, '').replace(/^./, (c) => c.toUpperCase())}</th><th scope="col">Published findings</th></tr></thead>
            <tbody>{items.map((it) => <tr key={it.key}><th scope="row">{it.label}</th><td>{it.count}</td></tr>)}</tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
