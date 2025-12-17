import { useState, useEffect } from 'react'
import { 
  Clock, Calendar, Power, Save, RefreshCw, Loader2, 
  Check, AlertCircle, Sun, Moon
} from 'lucide-react'
import styles from './WorkerSchedule.module.css'

const API_BASE = '/api'

const DAYS = [
  { id: 0, label: 'Mon', short: 'M' },
  { id: 1, label: 'Tue', short: 'T' },
  { id: 2, label: 'Wed', short: 'W' },
  { id: 3, label: 'Thu', short: 'T' },
  { id: 4, label: 'Fri', short: 'F' },
  { id: 5, label: 'Sat', short: 'S' },
  { id: 6, label: 'Sun', short: 'S' }
]

const TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Berlin',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Australia/Sydney'
]

export default function WorkerSchedule() {
  const [enabled, setEnabled] = useState(false)
  const [schedule, setSchedule] = useState({
    start_time: '22:00',
    end_time: '08:00',
    next_day: true,
    days: [0, 1, 2, 3, 4, 5, 6],
    timezone: 'UTC'
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    loadScheduleSettings()
  }, [])

  const loadScheduleSettings = async () => {
    setLoading(true)
    try {
      // Load from settings API
      const [enabledRes, scheduleRes] = await Promise.all([
        fetch(`${API_BASE}/settings/get/worker_schedule_enabled`),
        fetch(`${API_BASE}/settings/get/worker_default_schedule`)
      ])
      
      if (enabledRes.ok) {
        const data = await enabledRes.json()
        setEnabled(data.value === 'true')
      }
      
      if (scheduleRes.ok) {
        const data = await scheduleRes.json()
        if (data.value) {
          try {
            const parsed = typeof data.value === 'string' ? JSON.parse(data.value) : data.value
            setSchedule(parsed)
          } catch (e) {
            console.error('Failed to parse schedule:', e)
          }
        }
      }
    } catch (err) {
      console.error('Failed to load schedule settings:', err)
    } finally {
      setLoading(false)
    }
  }

  const saveSettings = async () => {
    setSaving(true)
    setError(null)
    setSuccess(false)
    
    try {
      await Promise.all([
        fetch(`${API_BASE}/settings/set`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            key: 'worker_schedule_enabled', 
            value: enabled.toString() 
          })
        }),
        fetch(`${API_BASE}/settings/set`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            key: 'worker_default_schedule', 
            value: JSON.stringify(schedule)
          })
        })
      ])
      
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const toggleDay = (dayId) => {
    setSchedule(prev => ({
      ...prev,
      days: prev.days.includes(dayId)
        ? prev.days.filter(d => d !== dayId)
        : [...prev.days, dayId].sort()
    }))
  }

  const updateTime = (field, value) => {
    setSchedule(prev => {
      const updated = { ...prev, [field]: value }
      // Auto-detect if end time is next day
      if (field === 'start_time' || field === 'end_time') {
        const start = parseInt(updated.start_time.replace(':', ''))
        const end = parseInt(updated.end_time.replace(':', ''))
        updated.next_day = end <= start
      }
      return updated
    })
  }

  // Calculate display text
  const getScheduleDescription = () => {
    if (!enabled) return 'Workers run 24/7'
    
    const dayNames = schedule.days.map(d => DAYS[d].label).join(', ')
    const timeRange = schedule.next_day 
      ? `${schedule.start_time} → ${schedule.end_time} (next day)`
      : `${schedule.start_time} → ${schedule.end_time}`
    
    return `Active ${timeRange} on ${dayNames}`
  }

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>
          <Loader2 size={16} className={styles.spin} /> Loading schedule settings...
        </div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <h4><Clock size={18} /> Worker Schedule</h4>
          <p className={styles.description}>
            Configure when workers are active. Useful for shared machines that you use during the day.
          </p>
        </div>
      </div>

      {/* Enable Toggle */}
      <div className={styles.enableRow}>
        <label className={styles.toggle}>
          <input 
            type="checkbox" 
            checked={enabled} 
            onChange={e => setEnabled(e.target.checked)} 
          />
          <span className={styles.slider}></span>
          <span className={styles.toggleLabel}>
            {enabled ? 'Scheduling enabled' : 'Scheduling disabled (24/7 operation)'}
          </span>
        </label>
      </div>

      {/* Schedule Configuration */}
      {enabled && (
        <div className={styles.scheduleConfig}>
          {/* Time Range */}
          <div className={styles.timeRange}>
            <div className={styles.timeField}>
              <label><Moon size={14} /> Start (workers resume)</label>
              <input 
                type="time" 
                value={schedule.start_time}
                onChange={e => updateTime('start_time', e.target.value)}
              />
            </div>
            <span className={styles.arrow}>→</span>
            <div className={styles.timeField}>
              <label><Sun size={14} /> End (workers pause)</label>
              <input 
                type="time" 
                value={schedule.end_time}
                onChange={e => updateTime('end_time', e.target.value)}
              />
            </div>
          </div>

          {schedule.next_day && (
            <div className={styles.nextDayNote}>
              <AlertCircle size={14} />
              End time is on the next day (overnight processing)
            </div>
          )}

          {/* Days */}
          <div className={styles.daysRow}>
            <label>Active Days</label>
            <div className={styles.dayButtons}>
              {DAYS.map(day => (
                <button
                  key={day.id}
                  className={`${styles.dayBtn} ${schedule.days.includes(day.id) ? styles.active : ''}`}
                  onClick={() => toggleDay(day.id)}
                  title={day.label}
                >
                  {day.short}
                </button>
              ))}
            </div>
          </div>

          {/* Timezone */}
          <div className={styles.timezoneRow}>
            <label>Timezone</label>
            <select 
              value={schedule.timezone}
              onChange={e => setSchedule(prev => ({ ...prev, timezone: e.target.value }))}
            >
              {TIMEZONES.map(tz => (
                <option key={tz} value={tz}>{tz}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* Summary */}
      <div className={styles.summary}>
        <Calendar size={14} />
        <span>{getScheduleDescription()}</span>
      </div>

      {/* Actions */}
      <div className={styles.actions}>
        {error && (
          <div className={styles.error}>
            <AlertCircle size={14} /> {error}
          </div>
        )}
        {success && (
          <div className={styles.success}>
            <Check size={14} /> Saved!
          </div>
        )}
        <button 
          className={styles.saveBtn}
          onClick={saveSettings}
          disabled={saving}
        >
          {saving ? (
            <><Loader2 size={14} className={styles.spin} /> Saving...</>
          ) : (
            <><Save size={14} /> Save Schedule</>
          )}
        </button>
      </div>
    </div>
  )
}
