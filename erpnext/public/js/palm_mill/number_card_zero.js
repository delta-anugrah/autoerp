// A number card worth Rp 0 renders as "Rp NaN".
//
// `frappe.utils.shorten_number` opens with `if (!number || isNaN(number)) return ""`,
// which is meant to pass null and undefined through as blank -- but 0 is falsy too, so
// a real zero comes back as an empty string. `number_card_widget.js` then does
// `parseFloat("")` -> NaN and hands that to `format_currency`, which prints the symbol
// against it: "Rp NaN". Only cards with a `currency` take that path, which is why the
// three money cards on the mill workspace show it and the plain counters do not.
//
// This is not a mill-specific bug -- it is upstream's, on any site whose currency cards
// can read zero. It shows up here first because a palm mill bills monthly: Accounts
// Receivable, Accounts Payable and Sales all sit at zero until the first invoice, so a
// freshly installed site greets its owner with three NaNs. FFB Purchase Value is the
// same card type and reads zero on day one too, before the first ticket.
//
// Patched here rather than in `frappe/utils/utils.js` for the reason every patch in this
// folder exists: editing core conflicts on each pull from version-16. Wrapping keeps the
// upstream function intact and lets a future Frappe fix simply make this a no-op.
const _shorten_number = frappe.utils.shorten_number;

frappe.utils.shorten_number = function (number, country, min_length = 4, max_no_of_decimals = 2) {
	// Keep upstream's contract for the values it actually meant to blank out. `isNaN`
	// covers null (Number(null) is 0, so null must be caught before the zero check),
	// undefined, "" and non-numeric strings.
	if (number === null || number === undefined || number === "" || isNaN(number)) {
		return "";
	}

	// The whole fix: a genuine zero is a number, not a blank. Returned as a string
	// because that is what the caller splits on -- `format_currency(parseFloat("0"))`
	// gives "Rp 0,00", where `parseFloat("")` gave NaN.
	if (Number(number) === 0) {
		return "0";
	}

	return _shorten_number.call(this, number, country, min_length, max_no_of_decimals);
};
