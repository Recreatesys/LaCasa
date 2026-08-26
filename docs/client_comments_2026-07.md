# Client Comments — "odoo comments_July2026.pptx" (13 Jul 2026)

Register of every comment in the deck, mapped to code, with status as of 26 Aug 2026.
Status: **DONE** = already shipped after the deck | **TODO** = needs work | **DECIDE** = needs a product decision first | **N/A** = not a code change.

---

## A. CRM / Opportunity

| # | Slide | Comment | Where | Status |
|---|-------|---------|-------|--------|
| C01 | 1 | Client Type should be set when creating the **client**, not asked on the opportunity | `res_partner.py` (no `client_type` field), `crm_lead.py:161` | **TODO** — add `client_type` to `res.partner`, default onto lead/SO from the partner |
| C02 | 2 | Event / Delivery Time should be a **time slot** (12:00–14:00) | `crm_lead.py` `event_time_start` / `event_time_end` | **DONE** |
| C03 | 3 | Need to cater an event/order spanning **a few days** | `crm_lead.py` `event_date_start` / `event_date_end` / `event_day_count` (≤7) | **DONE** |
| C04 | 4 | Sales picks a **preferred driver**; CS team finalises in EO | `crm_lead.call_van` labelled "Preferred Driver"; `lcs.event.order.call_van` editable | **VERIFY** — confirm EO re-sync doesn't overwrite the CS team's choice |
| C05a | 5 | **Service Type** — exact list + order (15 values) | `crm_lead.py:32 SERVICE_TYPE_SELECTION` | **TODO** — reorder + rename (Event–Buffet / Event–Cocktail / Event–Banquet, Staffing, Utensil Rental) |
| C05b | 5 | **Delivery Type** — exact list + order (6 values) | `crm_lead.py:50 DELIVERY_TYPE_SELECTION` | **TODO** — add Simple Set-up (round-trip / one-trip), Self pick-up; reorder |
| C05c | 5 | Setup Type → **Waiter Service**, yes/no | `waiter_service` Boolean | **DONE** |

## B. Products & Pricing

| # | Slide | Comment | Where | Status |
|---|-------|---------|-------|--------|
| C06 | 6 | Search products **by category** in the SO line | `static/src/js/product_field_search_limit.js` | **TODO** — add category to the product `_name_search` / autocomplete |
| C07 | 7 | Restructure product categories to **2 tiers** (Tray Food/Buffet, Canapes, Meal Box, Banquet + children) | `product.category` data — no LCS category data file exists | **TODO** — new category data + remap existing products (migration) |
| C08 | 8 | Auto-map the **delivery charge** from Event address + Delivery Type | District products in `corporate_party_set.xml:10-84`; no mapping logic | **TODO** — district model/mapping + auto-add the right delivery line |
| C09 | 9 | Don't discount delivery — **waive** it. Discount on specific items + "Delivery fee waived" | `free_delivery_product.xml`, standard Odoo discount wizard | **TODO** — `delivery_waived` flag + exclude delivery lines from global discount |
| C11 | 11 | Show the **HK$398 unit price** on the set line; don't make sales pick the package-fee line under Expand | `lcs_product_catalog/models/sale_order.py` `action_expand_sets` (container written to qty 1 / price 0) | **TODO** |
| C12 | 12 | Remove the **💡 recommendation note** wording from the order lines | `lcs_product_catalog/models/sale_order.py` | **DONE** `e6d0c90` — note line no longer created; migration clears draft/sent orders |
| C13 | 13 | Only 2 items chosen where 3 required — **no reminder** | `catering_set.py` `CateringSetRule` has `max_selection` only | **TODO** — add `min_selection` + validation on confirm |
| C14 | 14, 15 | Changing qty 50→100 on the package line doesn't update dish quantities; **Reload Sets should follow the changed line qty**, not "No. of Guests" | `sale_order.py` `action_reload_sets` / `_reload_sets_in_place` (both read `self.guest_count`) | **TODO** |
| C21a | 21 | Let sales **create/save their own package templates** | new | **DECIDE** |
| C21b | 21 | Show the **cost** of each food item on the line | `lcs_product_catalog/models/sale_order.py` | **DONE** `e6d0c90` — `lcs_unit_cost` / `lcs_line_cost` / `lcs_margin_pct`, salesman-only, `optional="hide"` |
| C21c | 21 | Price below X% → **manager approval** required | new | **DECIDE** — need the threshold and the approver group |

## C. Waiters / Equipment

| # | Slide | Comment | Where | Status |
|---|-------|---------|-------|--------|
| C16 | 16 | Waiter roster is **ops' input (EO)**; sales only shows "# waiters included" | `sale_waiter_line.py`, `sale_order_views.xml:74` Waiters tab | **TODO** — move the detail to EO, leave a count on the SO |
| C17 | 17 | Rename **Hardware → "Utensil & Equipment"** | `sale_hardware_line.py`, `sale_order_views.xml` | **DONE** `b5a847f` — labels + auto-generated SO section; migration re-stamps historical orders |

## D. Print / Preview / Portal

| # | Slide | Comment | Where | Status |
|---|-------|---------|-------|--------|
| C10a | 10 | **Email not working** | outgoing mail server config | **TODO** — server-side check |
| C10b | 10 | **Cc the salesperson** on outgoing mail | `static/src/js/composer_cc.js` (Cc field + per-user default) | **PARTIAL** — auto-seed Cc with the record's salesperson |
| C18 | 18 | Print menu: keep **only "LCS Quotation"** | `data/hide_default_prints.xml` | **DONE** |
| C19 | 19 | Too many preview/print formats — modify the **standard** one instead? | `report/*.xml` (3 templates) | **DECIDE** |
| C20 | 20 | Invoice/portal shows only "Down payment", **product items should show** | `sale_advance_payment_inv.py` (set name + dish notes appended) | **PARTIAL** — verify on the portal view |

## E. Event Order

| # | Slide | Comment | Where | Status |
|---|-------|---------|-------|--------|
| C23 | 23 | EO list should show the **current month only** | `event_order_views.xml` | **DONE** `07335b4` — "This Month" default filter + month/quarter date selector |
| C24a | 24 | Dish Overview: **food items only** (hide Delivery / Waiter Service) | `event_order_line.py` | **DONE** `07335b4` — stored `is_food_item` (non-storable goods only), removable default filter |
| C24b | 24 | Add a **date selection** for the chef in that view | `event_order_line_views.xml` | **DONE** `07335b4` — `date="event_date"` selector + Tomorrow shortcut |
| C24c | 24 | Rename group "Dish" → **"Category"** and group by category | `event_order_line.py`, views | **DONE** `07335b4` — stored `product_categ_id`; defaults to Category › Dish (two-level, keeps per-dish qty) |
| C25 | 25 | Qty should read **"2 × ½ GN tray"**, **"90 pcs"** — not a bare number | `event_order_line.py` `kitchen_qty` / `kitchen_uom` | **TODO** |
| C26a | 26 | Replace the EO list with **worksheets: Event / Drop-off**, each with its own columns (Kitchen assigned, Driver status, Waiter assigned, EO status) | `event_order.py` — no `kitchen_id`, `driver_status`, `waiter_ids` fields | **TODO** — new fields + 2 filtered list views |
| C26b | 26 | Generate a **catering order checklist** for CS (check with Prina) | new | **DECIDE** |
| C26c | 26 | How does CS **assign delivery** per order? | new | **DECIDE** |
| C26d | 26 | How does the event team **assign waiters** in the EO portal? | ties to C16 | **DECIDE** |

## F. Non-code / Project

| # | Slide | Item | Status |
|---|-------|------|--------|
| C27 | 27 | Re-input products (category/unit/price), user roles, template final check, verify packages, import old+current CRM data, website enquiry integration, cost input, accounting integration, security, revenue combination | **N/A** — data & config work stream |
| C28 | 28 | School project phase 1 (Jul–Aug 2026): site managers build the monthly menu in Odoo; monthly/weekly menu development | `lcs_school_portal` exists (`menu_template`, `menu_day`, `menu_generate_wizard`) | **VERIFY** |

---

## Progress log

- **26 Aug 2026 — Batch 1 (quick wins), deployed.** C12, C17, C21b, C23, C24a/b/c.
  Modules bumped: `lcs_crm_catering` 19.0.1.76.0, `lcs_event_order` 19.0.1.17.0,
  `lcs_product_catalog` 19.0.2.19.0.

### Open decisions blocking further work

1. **C19** — which print format survives? There are three today (LCS Quotation,
   PDF Quote, Quotation/Order). The client asks whether to modify the standard one
   instead of maintaining separate LCS templates.
2. **C21a** — should sales be able to save their own package templates, and are
   those private to the salesperson or shared across the team?
3. **C21c** — what discount % triggers manager approval, and which group approves?
4. **C26b/c/d** — the checklist, delivery-assignment and waiter-assignment flows.
   The deck itself defers these to a meeting ("need to check with Prina").
