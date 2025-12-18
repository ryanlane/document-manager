import { useState } from 'react'
import { 
  Check, 
  Loader2
} from 'lucide-react'
import styles from '../Settings.module.css'

const API_BASE = '/api'

export default function FileTypesTab({ 
  extensions, 
  setExtensions,
  saving,
  setSaving
}) {
  const [newExtension, setNewExtension] = useState('')

  const toggleExtension = (ext) => {
    if (extensions.includes(ext)) {
      setExtensions(extensions.filter(e => e !== ext))
    } else {
      setExtensions([...extensions, ext])
    }
  }

  const saveExtensions = async () => {
    setSaving(true)
    try {
      await fetch(`${API_BASE}/settings/extensions`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ extensions })
      })
    } catch (err) {
      alert('Failed to save extensions')
    }
    setSaving(false)
  }

  const addCustomExtension = () => {
    if (!newExtension) return
    const ext = newExtension.startsWith('.') ? newExtension : '.' + newExtension
    if (!extensions.includes(ext)) {
      setExtensions([...extensions, ext])
    }
    setNewExtension('')
  }

  return (
    <div className={styles.section}>
      <h2>File Types</h2>
      <p className={styles.description}>
        Select which file types to process and index.
      </p>

      <div className={styles.extCategories}>
        {[
          { name: 'Documents', exts: ['.txt', '.md', '.pdf', '.docx', '.doc', '.html', '.rtf'] },
          { name: 'Images', exts: ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'] },
          { name: 'E-books', exts: ['.epub', '.mobi'] },
          { name: 'Data', exts: ['.csv', '.json', '.xml', '.yaml'] }
        ].map(cat => (
          <div key={cat.name} className={styles.extCategory}>
            <h4>{cat.name}</h4>
            <div className={styles.extToggles}>
              {cat.exts.map(ext => (
                <label key={ext} className={styles.extToggle}>
                  <input
                    type="checkbox"
                    checked={extensions.includes(ext)}
                    onChange={() => toggleExtension(ext)}
                  />
                  <span>{ext}</span>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Custom Extension */}
      <div className={styles.customExt}>
        <input
          type="text"
          value={newExtension}
          onChange={(e) => setNewExtension(e.target.value)}
          placeholder="Add custom extension..."
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              addCustomExtension()
            }
          }}
        />
      </div>

      <div className={styles.actions}>
        <button className={styles.saveBtn} onClick={saveExtensions} disabled={saving}>
          {saving ? <Loader2 className={styles.spinner} size={16} /> : <Check size={16} />}
          Save File Types
        </button>
      </div>
    </div>
  )
}
