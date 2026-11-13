import {
  useState,
  type FormEvent,
} from 'react'

import AuthForm from '../components/auth/AuthForm.tsx'
import {
  getFormValue,
  validateAuthForm,
  type FieldErrors,
} from '../lib/authValidation.ts'
import {
  ApiError,
  api,
  type User,
} from '../lib/api.ts'

type AuthPageProps = {
  register?: boolean
  onAuthenticated: (user: User) => void
}

export default function AuthPage({
  register = false,
  onAuthenticated,
}: AuthPageProps) {
  const [errors, setErrors] = useState<FieldErrors>({})
  const [generalError, setGeneralError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    const data = new FormData(event.currentTarget)
    const email = getFormValue(data, 'email').trim()
    const password = getFormValue(data, 'password')
    const displayName = getFormValue(
      data,
      'display_name',
    ).trim()

    const nextErrors = validateAuthForm(
      email,
      password,
      displayName,
      register,
    )

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }

    setErrors({})
    setGeneralError('')
    setSubmitting(true)

    try {
      if (register) {
        await registerUser(email, password, displayName)
      }

      const user = await loginUser(email, password)

      onAuthenticated(user)
    } catch (error) {
      handleRequestError(error)
    } finally {
      setSubmitting(false)
    }
  }

  async function registerUser(
    email: string,
    password: string,
    displayName: string,
  ) {
    await api<User>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        display_name: displayName,
      }),
    })
  }

  async function loginUser(
    email: string,
    password: string,
  ) {
    return api<User>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
      }),
    })
  }

  function handleRequestError(error: unknown) {
    if (error instanceof ApiError) {
      setGeneralError(error.message)
      return
    }

    setGeneralError('Could not reach the server.')
  }

  return (
    <div className="auth-layout">
      <AuthForm
        register={register}
        errors={errors}
        generalError={generalError}
        submitting={submitting}
        onSubmit={submit}
      />
    </div>
  )
}
