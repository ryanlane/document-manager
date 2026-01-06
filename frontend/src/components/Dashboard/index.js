// Dashboard component exports
export { default as DashboardHeader } from './DashboardHeader'
export { default as RecentFilesSection } from './RecentFilesSection'
export { default as SecondaryStatsRow } from './SecondaryStatsRow'

// Note: The following components are deferred for future extraction due to complexity:
// - ToastNotificationStack - needs state management refactor
// - WorkerControlBar - complex with many toggles and state dependencies
// - DocLevelPipelineCard - requires shared StatCard and ProgressBar components
// - ChunkLevelPipelineCard - requires shared components and inheritance logic
//
// These will be extracted in a future phase after state management patterns are established.
