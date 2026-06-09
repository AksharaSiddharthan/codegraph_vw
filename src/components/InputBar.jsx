import { useState } from 'react'

export default function InputBar({ onAnalyze, disabled }) {
  const [source, setSource] = useState('')
  const [sourceType, setSourceType] = useState('github')

  const submit = (e) => {
    e.preventDefault()
    if (!source.trim()) return
    onAnalyze(source.trim(), sourceType)
  }

  return (
    <form className="input-bar" onSubmit={submit}>
      <select
        value={sourceType}
        onChange={(e) => setSourceType(e.target.value)}
        disabled={disabled}
      >
        <option value="github">GitHub URL</option>
        <option value="local">Local path</option>
      </select>
      <input
        type="text"
        value={source}
        onChange={(e) => setSource(e.target.value)}
        placeholder={
          sourceType === 'github'
            ? 'https://github.com/owner/repo'
            : '/absolute/path/to/project'
        }
        disabled={disabled}
      />
      <button type="submit" disabled={disabled}>
        {disabled ? 'Analyzing…' : 'Analyze'}
      </button>
    </form>
  )
}
