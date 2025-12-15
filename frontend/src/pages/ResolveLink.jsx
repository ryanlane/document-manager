import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

function ResolveLink() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const fromId = searchParams.get('from')
  const toPath = searchParams.get('to')

  useEffect(() => {
    if (!fromId || !toPath) {
      navigate('/')
      return
    }

    fetch(`/api/files/${fromId}/resolve?path=${encodeURIComponent(toPath)}`)
      .then(res => {
        if (!res.ok) throw new Error('Not found')
        return res.json()
      })
      .then(data => {
        navigate(`/document/${data.id}`, { replace: true })
      })
      .catch(() => {
        // If resolution fails, maybe show an error or go back
        alert(`Could not resolve link: ${toPath}`)
        navigate(-1)
      })
  }, [fromId, toPath, navigate])

  return (
    <div style={{ padding: '2rem', textAlign: 'center' }}>
      Resolving link...
    </div>
  )
}

export default ResolveLink
