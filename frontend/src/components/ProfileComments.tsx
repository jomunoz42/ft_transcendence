import {
  useState,
  type FormEvent,
} from 'react'

import SectionHeading from './SectionHeading.tsx'
import {
  api,
  getErrorMessage,
  type ProfileComment,
  type User,
} from '../lib/api.ts'

type ProfileCommentsProps = {
  user: User
  userId: number
  comments?: ProfileComment[]
  isFriend: boolean
  onReload: () => Promise<void>
}

export default function ProfileComments({
  user,
  userId,
  comments,
  isFriend,
  onReload,
}: ProfileCommentsProps) {
  const [commentBody, setCommentBody] = useState('')
  const [busy, setBusy] = useState(false)
  const [actionMessage, setActionMessage] = useState('')

  async function sendComment(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    const body = commentBody.trim()

    if (!body) {
      return
    }

    if (!isFriend) {
      return
    }

    setBusy(true)
    setActionMessage('')

    try {
      await api(`/api/v1/profiles/${userId}/comments`, {
        method: 'POST',
        body: JSON.stringify({
          body,
        }),
      })

      setCommentBody('')
      await onReload()
    } catch (reason) {
      const message = getErrorMessage(
        reason,
        'Could not post your comment.',
      )

      setActionMessage(message)
    } finally {
      setBusy(false)
    }
  }

  async function deleteComment(commentId: number) {
    setBusy(true)
    setActionMessage('')

    try {
      await api(
        `/api/v1/profiles/${userId}/comments/${commentId}`,
        {
          method: 'DELETE',
        },
      )

      await onReload()
    } catch (reason) {
      const message = getErrorMessage(
        reason,
        'Could not delete your comment.',
      )

      setActionMessage(message)
    } finally {
      setBusy(false)
    }
  }

  function renderDeleteButton(comment: ProfileComment) {
    if (comment.author_id !== user.id) {
      return null
    }

    return (
      <button
        className="text-button"
        type="button"
        disabled={busy}
        onClick={() => {
          void deleteComment(comment.id)
        }}
      >
        Delete
      </button>
    )
  }

  function renderComments() {
    if (!comments || comments.length === 0) {
      return (
        <p className="social-state">
          No comments yet.
        </p>
      )
    }

    return comments.map((comment) => (
      <article
        className="comment-item"
        key={comment.id}
      >
        <p>{comment.body}</p>

        <small>
          Listener #{comment.author_id}
        </small>

        {renderDeleteButton(comment)}
      </article>
    ))
  }

  function renderActionMessage() {
    if (!actionMessage) {
      return null
    }

    return (
      <p
        className="social-state"
        role="alert"
      >
        {actionMessage}
      </p>
    )
  }

  function renderConversation() {
    if (!isFriend) {
      return (
        <p className="social-state">
          Comments are available between friends.
        </p>
      )
    }

    const commentIsEmpty = !commentBody.trim()
    const postButtonDisabled = busy || commentIsEmpty

    return (
      <>
        <form
          className="comment-form"
          onSubmit={sendComment}
        >
          <textarea
            value={commentBody}
            rows={3}
            maxLength={2000}
            placeholder="Say something about their list…"
            onChange={(event) => {
              setCommentBody(event.target.value)
            }}
          />

          <button
            className="button button-dark"
            type="submit"
            disabled={postButtonDisabled}
          >
            Post comment
          </button>
        </form>

        <div className="comments-list">
          {renderComments()}
        </div>
      </>
    )
  }

  return (
    <section className="card social-card">
      <SectionHeading
        eyebrow="CONVERSATION"
        title="Comments"
      />

      {renderConversation()}
      {renderActionMessage()}
    </section>
  )
}
