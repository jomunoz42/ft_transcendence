import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'

import PrivacySettings from '../src/components/PrivacySettings.tsx'
import { json } from './notificationsServer.ts'

const requestBody = {
  detail: 'Check your email',
  expires_at: '2026-11-24T22:15:00+00:00',
  cooldown_seconds: 300,
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
})

it('downloads the attachment with the server filename and reports email failure separately', async () => {
  const payload = { format_version: 3, account: { display_name: 'Alice' }, messages: [] }
  const fetch = vi.mocked(globalThis.fetch)
  fetch.mockResolvedValue(new Response(JSON.stringify(payload), {
    headers: {
      'Content-Disposition': 'attachment; filename="myplaylist-data.json"',
      'X-Confirmation-Email': 'failed',
      'Content-Type': 'application/json',
    },
  }))
  const createObjectURL = vi.fn(() => 'blob:private-export')
  const revokeObjectURL = vi.fn()
  vi.stubGlobal('URL', Object.assign(class extends URL {}, { createObjectURL, revokeObjectURL }))
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    expect(this.download).toBe('myplaylist-data.json')
    expect(this.href).toBe('blob:private-export')
  })

  render(<PrivacySettings onAccountDeleted={vi.fn()} />)
  await userEvent.setup().click(screen.getByRole('button', { name: 'Download my data' }))
  expect(await screen.findByText('Your data was downloaded. The confirmation email could not be sent.')).toBeTruthy()
  expect(click).toHaveBeenCalledOnce()
  expect(createObjectURL).toHaveBeenCalledOnce()
  expect(revokeObjectURL).toHaveBeenCalledWith('blob:private-export')
  expect(fetch).toHaveBeenCalledWith('/api/v1/privacy/export', expect.objectContaining({ method: 'POST', credentials: 'include', cache: 'no-store' }))
})

it('reports export authorization and server failures without starting a download', async () => {
  const fetch = vi.mocked(globalThis.fetch)
  fetch.mockResolvedValue(json({ detail: 'Not authenticated' }, 401))
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click')
  render(<PrivacySettings onAccountDeleted={vi.fn()} />)
  await userEvent.setup().click(screen.getByRole('button', { name: 'Download my data' }))
  expect(await screen.findByText('Not authenticated')).toBeTruthy()
  expect(click).not.toHaveBeenCalled()
})

it('requests email, shows expiry and cooldown, requires DELETE, and confirms with a body token', async () => {
  const fetch = vi.mocked(globalThis.fetch)
  fetch.mockResolvedValueOnce(json(requestBody, 202)).mockResolvedValueOnce(new Response(null, { status: 204 }))
  const deleted = vi.fn()
  render(<PrivacySettings onAccountDeleted={deleted} />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Email me a deletion token' }))
  expect(await screen.findByText(/Confirmation email sent/)).toBeTruthy()
  expect(screen.getByText(/You can request another email in 5 minutes/)).toBeTruthy()
  expect(screen.getByText(/The token expires/)).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Email me a deletion token' }).hasAttribute('disabled')).toBe(true)
  const confirm = screen.getByRole('button', { name: 'Permanently delete account' })
  expect(confirm.hasAttribute('disabled')).toBe(true)
  await user.type(screen.getByLabelText('Token from your email'), 'private-token')
  await user.type(screen.getByRole('textbox', { name: /Type DELETE/ }), 'DELETE')
  await user.click(confirm)
  await waitFor(() => expect(deleted).toHaveBeenCalledOnce())
  expect(fetch).toHaveBeenNthCalledWith(2, '/api/v1/privacy/deletion-confirm', expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({ token: 'private-token', confirmation: 'DELETE' }),
  }))
  expect(window.location.search).toBe('')
  expect(window.localStorage.length).toBe(0)
})

it('cancels without confirming and erases the token from the form', async () => {
  const fetch = vi.mocked(globalThis.fetch)
  fetch.mockResolvedValue(json(requestBody, 202))
  render(<PrivacySettings onAccountDeleted={vi.fn()} />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Email me a deletion token' }))
  await screen.findByLabelText('Token from your email')
  await user.type(screen.getByLabelText('Token from your email'), 'private-token')
  await user.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByLabelText('Token from your email')).toBeNull()
  expect(screen.getByText(/Deletion was not confirmed/)).toBeTruthy()
  expect(fetch).toHaveBeenCalledOnce()
})

it('shows email delivery failure and keeps confirmation closed', async () => {
  const fetch = vi.mocked(globalThis.fetch)
  fetch.mockResolvedValue(json({ detail: 'Deletion confirmation email could not be sent' }, 503))
  render(<PrivacySettings onAccountDeleted={vi.fn()} />)
  await userEvent.setup().click(screen.getByRole('button', { name: 'Email me a deletion token' }))
  expect(await screen.findByText('Deletion confirmation email could not be sent')).toBeTruthy()
  expect(screen.queryByLabelText('Token from your email')).toBeNull()
})

it('restores the request cooldown from a server rate-limit response', async () => {
  const fetch = vi.mocked(globalThis.fetch)
  fetch.mockResolvedValue(new Response(JSON.stringify({ detail: 'Wait before requesting another deletion email' }), {
    status: 429,
    headers: { 'Content-Type': 'application/json', 'Retry-After': '120' },
  }))
  render(<PrivacySettings onAccountDeleted={vi.fn()} />)
  await userEvent.setup().click(screen.getByRole('button', { name: 'Email me a deletion token' }))
  expect(await screen.findByText('Wait before requesting another deletion email')).toBeTruthy()
  expect(screen.getByText(/You can request another email in 2 minutes/)).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Email me a deletion token' }).hasAttribute('disabled')).toBe(true)
  await userEvent.setup().click(screen.getByRole('button', { name: 'I already have a token' }))
  expect(screen.getByLabelText('Token from your email')).toBeTruthy()
  expect(screen.getByText(/Tokens expire 15 minutes after the email request/)).toBeTruthy()
})

it('accepts an existing emailed token after a page reload without requesting another email', async () => {
  const fetch = vi.mocked(globalThis.fetch)
  fetch.mockResolvedValue(new Response(null, { status: 204 }))
  const deleted = vi.fn()
  render(<PrivacySettings onAccountDeleted={deleted} />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'I already have a token' }))
  await user.type(screen.getByLabelText('Token from your email'), 'mailed-token')
  await user.type(screen.getByRole('textbox', { name: /Type DELETE/ }), 'DELETE')
  await user.click(screen.getByRole('button', { name: 'Permanently delete account' }))
  await waitFor(() => expect(deleted).toHaveBeenCalledOnce())
  expect(fetch).toHaveBeenCalledOnce()
  expect(fetch).toHaveBeenCalledWith('/api/v1/privacy/deletion-confirm', expect.objectContaining({
    body: JSON.stringify({ token: 'mailed-token', confirmation: 'DELETE' }),
  }))
})

it('handles expired or invalid tokens without clearing authentication', async () => {
  const fetch = vi.mocked(globalThis.fetch)
  fetch.mockResolvedValueOnce(json(requestBody, 202)).mockResolvedValueOnce(json({ detail: 'Invalid or expired deletion confirmation' }, 400))
  const deleted = vi.fn()
  render(<PrivacySettings onAccountDeleted={deleted} />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Email me a deletion token' }))
  await screen.findByLabelText('Token from your email')
  await user.type(screen.getByLabelText('Token from your email'), 'expired-token')
  await user.type(screen.getByRole('textbox', { name: /Type DELETE/ }), 'DELETE')
  await user.click(screen.getByRole('button', { name: 'Permanently delete account' }))
  expect(await screen.findByText('Invalid or expired deletion confirmation')).toBeTruthy()
  expect(deleted).not.toHaveBeenCalled()
})
