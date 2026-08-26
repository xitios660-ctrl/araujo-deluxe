// Test IDs for checkout, shipping calculator and order confirmation.

export const SHIPPING_CALC = {
	container: 'shipping-calculator',
	toggle: 'shipping-calc-toggle',
	cepInput: 'shipping-cep-input',
	result: 'shipping-calc-result',
	options: 'shipping-options',
	error: 'shipping-error',
};

export const CHECKOUT = {
	page: 'checkout-page',
	backLink: 'checkout-back-link',
	nameInput: 'checkout-name-input',
	phoneInput: 'checkout-phone-input',
	emailInput: 'checkout-email-input',
	cepInput: 'checkout-cep-input',
	cepError: 'checkout-cep-error',
	streetInput: 'checkout-street-input',
	numberInput: 'checkout-number-input',
	complementInput: 'checkout-complement-input',
	neighborhoodInput: 'checkout-neighborhood-input',
	cityInput: 'checkout-city-input',
	stateInput: 'checkout-state-input',
	shippingOptions: 'checkout-shipping-options',
	summary: 'checkout-summary',
	subtotal: 'checkout-subtotal',
	shippingPrice: 'checkout-shipping-price',
	total: 'checkout-total',
	submitButton: 'checkout-submit-button',
};

export const ORDER_CONFIRMATION = {
	page: 'order-confirmation',
	orderNumber: 'confirmation-order-number',
	whatsappButton: 'confirmation-whatsapp-button',
	backLink: 'confirmation-back-link',
};

export const CART_CHECKOUT = {
	checkoutButton: 'cart-checkout-button',
	whatsappLink: 'cart-whatsapp-link',
};

export const TRACKING = {
	page: 'track-order-page',
	searchInput: 'tracking-search-input',
	searchButton: 'tracking-search-button',
	error: 'tracking-error',
	result: 'tracking-result',
	orderNumber: 'tracking-order-number',
	whatsappButton: 'tracking-whatsapp-button',
};

export const ADMIN = {
	loginPage: 'admin-login-page',
	emailInput: 'admin-email-input',
	passwordInput: 'admin-password-input',
	loginButton: 'admin-login-button',
	loginError: 'admin-login-error',
	page: 'admin-page',
	ordersTable: 'admin-orders-table',
	refreshButton: 'admin-refresh-button',
	logoutButton: 'admin-logout-button',
	newOrdersBell: 'admin-new-orders-bell',
	newOrdersCount: 'admin-new-orders-count',
	// per order: admin-order-{order_number}, admin-status-select-{order_number}
};
