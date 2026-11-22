/**
 * Address validation - plain functions, no schema library.
 *
 * Mirrors the backend's own rules so the user gets an inline message instead of
 * a 400, while the server stays the authority.
 */

const MOBILE = /^(\+91)?[6-9]\d{9}$/;
const PINCODE = /^[1-9]\d{5}$/;

export function validateAddress(values) {
  const errors = {};

  if (!values.recipient_name || !values.recipient_name.trim()) {
    errors.recipient_name = "Enter the recipient's name";
  } else if (values.recipient_name.trim().length < 2) {
    errors.recipient_name = "That name looks too short";
  }

  const mobile = (values.recipient_mobile || "").replace(/[\s-]/g, "");
  if (!mobile) errors.recipient_mobile = "Enter a mobile number";
  else if (!MOBILE.test(mobile)) {
    errors.recipient_mobile = "Enter a 10-digit Indian mobile, or +91 followed by 10 digits";
  }

  if (!values.line1 || !values.line1.trim()) errors.line1 = "Enter the flat or house number";

  if (!values.pincode || !values.pincode.trim()) errors.pincode = "Enter the pincode";
  else if (!PINCODE.test(values.pincode.trim())) {
    errors.pincode = "A pincode has 6 digits and cannot start with 0";
  }

  if (!values.city || !values.city.trim()) errors.city = "Enter the city";
  if (!values.state || !values.state.trim()) errors.state = "Enter the state";

  return errors;
}

export const isAddressValid = (errors) => Object.keys(errors).length === 0;
