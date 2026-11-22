/** Profile edits - name and optional email. */

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function validateProfile(values) {
  const errors = {};
  if (!values.full_name || !values.full_name.trim()) errors.full_name = "Enter your name";
  else if (values.full_name.trim().length < 2) errors.full_name = "That name looks too short";

  if (values.email && values.email.trim() && !EMAIL.test(values.email.trim())) {
    errors.email = "Enter a valid email address";
  }
  return errors;
}

export const isProfileValid = (errors) => Object.keys(errors).length === 0;
