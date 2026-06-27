export default function TableBlock({ table }) {
  if (!table || !table.rows?.length) return null

  return (
    <div className="table-block">
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {table.columns.map(col => <th key={col}>{col}</th>)}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, i) => (
              <tr key={i}>
                {table.columns.map((col, idx) => (
                  <td key={col} className={idx === 0 ? 'td-label' : 'td-num'}>
                    {typeof row[col] === 'number' ? row[col].toLocaleString('it-IT') : row[col]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
