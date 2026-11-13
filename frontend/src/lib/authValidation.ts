export type FieldName =
  | 'display_name'
  | 'email'
  | 'password'

export type FieldErrors = Partial<
  Record<FieldName, string>
>

export function getFormValue(
  data: FormData,
  field: string,
) {
  const value = data.get(field)

  if (typeof value !== 'string') {
    return ''
  }

  return value
}

function hasValidEmailFormat(email: string) {
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

  return emailPattern.test(email)
}

function validateEmail(
  email: string,
  errors: FieldErrors,
) {
  if (hasValidEmailFormat(email)) {
    return
  }

  errors.email = 'Enter a valid email address.'
}

function validatePassword(
  password: string,
  errors: FieldErrors,
) {
  if (password.length < 8) {
    errors.password = 'Password must be 8 to 128 characters.'
    return
  }

  if (password.length > 128) {
    errors.password = 'Password must be 8 to 128 characters.'
  }
}

function validateDisplayName(
  displayName: string,
  register: boolean,
  errors: FieldErrors,
) {
  if (!register) {
    return
  }

  if (displayName) {
    return
  }

  errors.display_name = 'Display name is required.'
}

export function validateAuthForm(
  email: string,
  password: string,
  displayName: string,
  register: boolean,
) {
  const errors: FieldErrors = {}

  validateEmail(email, errors)
  validatePassword(password, errors)
  validateDisplayName(
    displayName,
    register,
    errors,
  )

  return errors
}
