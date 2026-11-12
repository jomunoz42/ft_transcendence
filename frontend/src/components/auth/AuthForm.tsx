import type { FormEvent } from 'react'

import type { Route } from '../../app/routes.tsx'
import logoIcon from '../../assets/icons/logoIcon.png'
import type { FieldErrors } from '../../lib/authValidation.ts'
import Link from '../Link.tsx'

type AuthFormProps = {
  register: boolean
  errors: FieldErrors
  generalError: string
  submitting: boolean
  onSubmit: (
    event: FormEvent<HTMLFormElement>,
  ) => Promise<void>
}

type FieldErrorProps = {
  id: string
  message?: string
}

function getErrorId(
  message: string | undefined,
  id: string,
) {
  if (!message) {
    return undefined
  }

  return id
}

function FieldError({
  id,
  message,
}: FieldErrorProps) {
  if (!message) {
    return null
  }

  return (
    <span
      id={id}
      className="field-error"
      role="alert"
    >
      {message}
    </span>
  )
}

function DisplayNameField({
  visible,
  error,
}: {
  visible: boolean
  error?: string
}) {
  if (!visible) {
    return null
  }

  const errorId = 'register-name-error'
  const describedBy = getErrorId(error, errorId)

  return (
    <label className="field-label">
      Display name

      <input
        name="display_name"
        autoComplete="nickname"
        required
        minLength={1}
        maxLength={100}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
      />

      <FieldError
        id={errorId}
        message={error}
      />
    </label>
  )
}

function EmailField({
  error,
}: {
  error?: string
}) {
  const errorId = 'auth-email-error'
  const describedBy = getErrorId(error, errorId)

  return (
    <label className="field-label">
      Email address

      <input
        name="email"
        type="email"
        autoComplete="email"
        placeholder="you@example.com"
        required
        maxLength={320}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
      />

      <FieldError
        id={errorId}
        message={error}
      />
    </label>
  )
}

function PasswordField({
  register,
  error,
}: {
  register: boolean
  error?: string
}) {
  let autoComplete = 'current-password'

  if (register) {
    autoComplete = 'new-password'
  }

  const errorId = 'auth-password-error'
  const describedBy = getErrorId(error, errorId)

  return (
    <label className="field-label">
      Password

      <input
        name="password"
        type="password"
        autoComplete={autoComplete}
        minLength={8}
        maxLength={128}
        required
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
      />

      <FieldError
        id={errorId}
        message={error}
      />
    </label>
  )
}

function GeneralError({
  message,
}: {
  message: string
}) {
  if (!message) {
    return null
  }

  return (
    <p
      className="form-error"
      role="alert"
    >
      {message}
    </p>
  )
}

function AuthSwitch({
  register,
}: {
  register: boolean
}) {
  let message = 'New to MyPlaylist?'
  let linkText = 'Create an account'
  let destination: Route = '/register'

  if (register) {
    message = 'Already have an account?'
    linkText = 'Sign in'
    destination = '/login'
  }

  return (
    <p className="auth-switch">
      {message}{' '}

      <Link to={destination}>
        {linkText}
      </Link>
    </p>
  )
}

export default function AuthForm({
  register,
  errors,
  generalError,
  submitting,
  onSubmit,
}: AuthFormProps) {
  let buttonLabel = 'Sign in'

  if (register) {
    buttonLabel = 'Create account'
  }

  if (submitting) {
    buttonLabel = 'Please wait…'
  }

  return (
    <section className="auth-form-side">
      <div className="auth-form-wrap">
        <div className="auth-heading">
          <img
            src={logoIcon}
            alt=""
          />

          <h1>Welcome to MyPlaylist</h1>
        </div>

        <form
          onSubmit={onSubmit}
          className="auth-form"
        >
          <DisplayNameField
            visible={register}
            error={errors.display_name}
          />

          <EmailField error={errors.email} />

          <PasswordField
            register={register}
            error={errors.password}
          />

          <GeneralError message={generalError} />

          <button
            className="button button-dark auth-submit"
            type="submit"
            disabled={submitting}
          >
            {buttonLabel}
            <span>→</span>
          </button>
        </form>

        <AuthSwitch register={register} />
      </div>
    </section>
  )
}