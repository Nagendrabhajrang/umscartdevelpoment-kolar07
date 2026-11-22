/** Checkout guard rails that the server also enforces. */

export function validateCheckout({ addressId, preview }) {
  const errors = {};
  if (!addressId) errors.address = "Choose a delivery address";
  if (preview) {
    if (preview.item_count === 0) errors.cart = "Your cart is empty";
    if (preview.store_open === false) errors.store = "The store is closed right now";
    if (preview.minimum_order_met === false) {
      errors.minimum = `Minimum order is Rs ${preview.minimum_order_value}`;
    }
  }
  return errors;
}

export const isCheckoutValid = (errors) => Object.keys(errors).length === 0;
