import {
  getActionClassName,
  getActionLabel,
  getRelationshipActions,
  type DirectoryProfile,
  type RelationshipAction,
  type RelationshipState,
} from '../../lib/friends.ts'

type RelationshipActionsProps = {
  profile: DirectoryProfile
  relationship: RelationshipState
  working: boolean
  onAction: (
    userId: number,
    action: RelationshipAction,
  ) => void
}

export default function RelationshipActions({
  profile,
  relationship,
  working,
  onAction,
}: RelationshipActionsProps) {
  const actions = getRelationshipActions(relationship)

  return (
    <div className="relationship-actions">
      {actions.map((action) => (
        <button
          key={action}
          className={getActionClassName(action)}
          type="button"
          disabled={working}
          onClick={() => {
            onAction(profile.user_id, action)
          }}
        >
          {getActionLabel(action)}
        </button>
      ))}
    </div>
  )
}