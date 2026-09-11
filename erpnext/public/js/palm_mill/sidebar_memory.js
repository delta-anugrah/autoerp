// Frappe's sidebar is sticky only in memory: on a reload or a pasted URL the resolver
// forgets which sidebar you were in and falls back to the DocType's module, so Batch
// opened from Pabrik Kelapa Sawit re-homes to Stock. Remember the last sidebar and, when
// it links the target, restore it before the module fallback runs.
const KEY = "last_sidebar";
const proto = frappe.ui.Sidebar.prototype;

const _setup = proto.setup;
proto.setup = function (title) {
	// only remember real sidebars; the module-name fallbacks ("Accounts") aren't ones
	if (title && frappe.boot.workspace_sidebar_item?.[title.toLowerCase()]) {
		try {
			localStorage.setItem(KEY, title);
		} catch (e) {
			// private mode
		}
	}
	return _setup.call(this, title);
};

const _set = proto.set_workspace_sidebar;
proto.set_workspace_sidebar = function (router) {
	if (!this.sidebar_title) {
		let last;
		try {
			last = localStorage.getItem(KEY);
		} catch (e) {
			// private mode
		}
		const entity = frappe.get_route()[1];
		const candidates = entity ? this.get_workspace_sidebars(entity) : [];
		if (last && candidates.includes(last)) {
			// Reports and Pages re-resolve after they load (query_report.js, pageview.js) and
			// are guarded by this list — Frappe's own resolver sets it before it decides.
			this.preferred_sidebars = candidates;
			this.setup(last);
			return;
		}
	}
	return _set.call(this, router);
};
