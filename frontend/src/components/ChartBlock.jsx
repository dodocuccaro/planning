import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

export default function ChartBlock({ chart }) {
  if (!chart || !chart.data?.length) return null

  return (
    <div className="chart-block">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chart.data} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey={chart.x_key} tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip formatter={(v) => v.toLocaleString('it-IT')} />
          <Legend />
          {chart.bars.map(b => (
            <Bar key={b.key} dataKey={b.key} fill={b.color} radius={[3, 3, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
