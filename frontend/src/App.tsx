import { Link } from 'react-router-dom'

const areas = [['Public', '/public'], ['Office', '/office'], ['Warehouse', '/warehouse'], ['Technician', '/technician'], ['Support', '/support'], ['Director', '/director']]

export function HomePage() {
  return <main className="home"><p className="eyebrow">Solar Installation Management</p><h1>SunPower Solutions</h1><p>Project scaffold is ready. Choose an area to explore its placeholder screen.</p><nav>{areas.map(([label, path]) => <Link className="card" key={path} to={path}><span>{label}</span><span aria-hidden="true">→</span></Link>)}</nav></main>
}
