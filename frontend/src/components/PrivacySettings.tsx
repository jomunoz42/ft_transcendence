import { useEffect, useRef, useState } from 'react'

import SectionHeading from './SectionHeading.tsx'
import { ApiError, api, getErrorMessage } from '../lib/api.ts'
import { downloadPrivacyExport, type DeletionRequest } from '../lib/privacy.ts'

type Props = { onAccountDeleted: () => void }

function requestError(error: unknown) {
  return getErrorMessage(error, 'Could not send the confirmation email. Please try again.')
}

export default function PrivacySettings({ onAccountDeleted }: Props) {
  const [exporting, setExporting] = useState(false)
  const [exportMessage, setExportMessage] = useState('')
  const [requesting, setRequesting] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [deletionOpen, setDeletionOpen] = useState(false)
  const [expiresAt, setExpiresAt] = useState('')
  const [cooldownUntil, setCooldownUntil] = useState(0)
  const [now, setNow] = useState(0)
  const [token, setToken] = useState('')
  const [phrase, setPhrase] = useState('')
  const [deletionMessage, setDeletionMessage] = useState('')
  const busy = useRef(false)

  useEffect(() => {
    if (cooldownUntil <= now) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [cooldownUntil, now])

  const remainingSeconds = Math.max(0, Math.ceil((cooldownUntil - now) / 1000))
  const cooldownText = remainingSeconds > 0
    ? `You can request another email in ${Math.ceil(remainingSeconds / 60)} minute${remainingSeconds > 60 ? 's' : ''}.`
    : 'You can request another email after a five-minute cooldown.'

  async function exportData() {
    if (busy.current) return
    busy.current = true
    setExporting(true)
    setExportMessage('')
    try {
      const emailStatus = await downloadPrivacyExport()
      setExportMessage(emailStatus === 'failed'
        ? 'Your data was downloaded. The confirmation email could not be sent.'
        : 'Your data was downloaded. A confirmation email was attempted.')
    } catch (error) {
      setExportMessage(getErrorMessage(error, 'Could not download your data.'))
    } finally {
      busy.current = false
      setExporting(false)
    }
  }

  async function requestDeletion() {
    if (busy.current || remainingSeconds > 0) return
    busy.current = true
    setRequesting(true)
    setDeletionMessage('')
    try {
      const result = await api<DeletionRequest>('/api/v1/privacy/deletion-request', { method: 'POST' })
      setExpiresAt(result.expires_at)
      setCooldownUntil(Date.now() + result.cooldown_seconds * 1000)
      setNow(Date.now())
      setToken('')
      setPhrase('')
      setDeletionOpen(true)
      setDeletionMessage('Confirmation email sent. Enter the token from that email below.')
    } catch (error) {
      if (error instanceof ApiError && error.status === 429 && error.retryAfterSeconds !== null) {
        setCooldownUntil(Date.now() + error.retryAfterSeconds * 1000)
        setNow(Date.now())
      }
      setDeletionMessage(requestError(error))
    } finally {
      busy.current = false
      setRequesting(false)
    }
  }

  async function confirmDeletion() {
    if (busy.current || !token.trim() || phrase !== 'DELETE') return
    busy.current = true
    setConfirming(true)
    setDeletionMessage('')
    try {
      await api<void>('/api/v1/privacy/deletion-confirm', {
        method: 'POST',
        body: JSON.stringify({ token: token.trim(), confirmation: phrase }),
      })
      setToken('')
      setPhrase('')
      onAccountDeleted()
    } catch (error) {
      setDeletionMessage(getErrorMessage(error, 'Could not confirm account deletion.'))
    } finally {
      busy.current = false
      setConfirming(false)
    }
  }

  function cancelDeletion() {
    if (busy.current) return
    setDeletionOpen(false)
    setToken('')
    setPhrase('')
    setDeletionMessage('Deletion was not confirmed. Your account remains active.')
  }

  return (
    <section className="card settings-card settings-privacy-card">
      <SectionHeading eyebrow="YOUR DATA" title="Privacy and account" />

      <div className="privacy-action">
        <h3>Download your data</h3>
        <p>The JSON download includes your account and profile, Top 10, friendships, blocks, comments, reactions, and received notifications. It excludes passwords, sessions, and other people’s private information.</p>
        <p>We attempt to email a confirmation. Your download remains available if that email fails.</p>
        <button className="button button-outline" type="button" disabled={exporting || requesting || confirming} onClick={() => void exportData()}>
          {exporting ? 'Preparing download…' : 'Download my data'}
        </button>
        {exportMessage && <p role="status" className="settings-save-message">{exportMessage}</p>}
      </div>

      <div className="privacy-action privacy-delete">
        <h3>Delete your account</h3>
        <p>Deletion is permanent. Your profile, Top 10, comments, reactions, friendships, blocks, notifications, and sessions will be removed. Shared songs and other people’s accounts remain.</p>
        <p>We send a confirmation token to your account email. It expires after 15 minutes. {cooldownText}</p>
        <button className="button button-outline" type="button" disabled={requesting || confirming || exporting || remainingSeconds > 0} onClick={() => void requestDeletion()}>
          {requesting ? 'Sending email…' : 'Email me a deletion token'}
        </button>
        {!deletionOpen && (
          <button className="text-button privacy-existing-token" type="button" disabled={requesting || confirming} onClick={() => {
            setDeletionOpen(true)
            setDeletionMessage('')
          }}>
            I already have a token
          </button>
        )}

        {deletionOpen && (
          <div className="privacy-confirmation">
            <p>{expiresAt
              ? `The token expires ${new Date(expiresAt).toLocaleString()}.`
              : 'Tokens expire 15 minutes after the email request.'} If you did not request deletion, cancel or leave this page. No account data is deleted without confirmation.</p>
            <label className="field-label">
              Token from your email
              <input type="password" autoComplete="off" spellCheck={false} maxLength={2048} value={token} disabled={confirming} onChange={(event) => setToken(event.target.value)} />
            </label>
            <label className="field-label">
              Type DELETE to confirm permanent deletion
              <input autoComplete="off" spellCheck={false} value={phrase} disabled={confirming} onChange={(event) => setPhrase(event.target.value)} />
            </label>
            <div className="privacy-buttons">
              <button className="button button-outline" type="button" disabled={confirming} onClick={cancelDeletion}>Cancel</button>
              <button className="button button-dark" type="button" disabled={confirming || phrase !== 'DELETE' || !token.trim()} onClick={() => void confirmDeletion()}>
                {confirming ? 'Deleting account…' : 'Permanently delete account'}
              </button>
            </div>
          </div>
        )}
        {deletionMessage && <p role="status" className="settings-save-message">{deletionMessage}</p>}
      </div>
    </section>
  )
}
