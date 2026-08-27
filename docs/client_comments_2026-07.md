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
| C05a | 5 | **Service Type** — exact list + order (15 values) | `crm_lead.py SERVICE_TYPE_SELECTION` | **DONE** — 15/15 match, verified live. Keys kept where the concept survives (relabel only); `event_banquet` added; `sit_down_menu` + `event` remapped to it by pre-migration (33 rows × 3 tables). |
| C05b | 5 | **Delivery Type** — exact list + order (6 values) | `crm_lead.py DELIVERY_TYPE_SELECTION` | **DONE** — 6/6 match, verified live. Purely additive + reorder; all three existing keys survive, so no data migration was needed. |
| C05c | 5 | Setup Type → **Waiter Service**, yes/no | `waiter_service` Boolean | **DONE** |

## B. Products & Pricing

| # | Slide | Comment | Where | Status |
|---|-------|---------|-------|--------|
| C06 | 6 | Search products **by category** in the SO line | `static/src/js/product_field_search_limit.js` | **TODO** — add category to the product `_name_search` / autocomplete |
| C07 | 7 | Restructure product categories to **2 tiers** (Tray Food/Buffet, Canapes, Meal Box, Banquet + children) | `product.category` on LaCasa_Odoo19 | **DONE** — verified live 26 Aug: the exact tree the client specified already exists, and every product except 67 is filed under it. My first pass read this as TODO off the deck's screenshot (`G. Rice & Pasta`), which predates the work. |
| C07b | 7 | Residual: 67 products still sit on the bare `LCS Dishes` root (mostly desserts + 4 banquet mains + 1 wine), and ~12 legacy flat categories (`A. Salad / Soup`, `G. Rice & Pasta`, …) are now empty | data | **CLIENT** — filing each dessert under `Canapes / Sweet` vs `Buffet / Dessert` vs `Banquet / Dessert` depends on which set sells it. Folds into the C27 product re-input. Note: most of the 67 are **duplicated pairs**. |
| C08 | 8 | Auto-map the **delivery charge** from Event address + Delivery Type | District products in `corporate_party_set.xml:10-84`; no mapping logic | **TODO** — district model/mapping + auto-add the right delivery line |
| C09 | 9 | Don't discount delivery — **waive** it. Discount on specific items + "Delivery fee waived" | `free_delivery_product.xml`, standard Odoo discount wizard | **TODO** — `delivery_waived` flag + exclude delivery lines from global discount |
| C11 | 11 | Show the **HK$398 unit price** on the set line; don't make sales pick the package-fee line under Expand | `catering_set.py`, `sale_order.py` | **DONE** `b6fe2c5` — new `is_package_fee`; single-fee sets fold onto the container (`100 × $398`). Flat-fee sets stay at qty 1; Cocktail Party's 4 tiers keep the pick. |
| C12 | 12 | Remove the **💡 recommendation note** wording from the order lines | `lcs_product_catalog/models/sale_order.py` | **DONE** `e6d0c90` — note line no longer created; migration clears draft/sent orders |
| C13 | 13 | Only 2 items chosen where 3 required — **no reminder** | `catering_set.py`, `sale_order.py` | **DONE** `b6fe2c5` — rules re-keyed to `section` (no rule ever had a `category_id`), `min_selection` added, live banner + blocking `action_confirm`. Dead `_get_selected_dish_count` removed. |
| C14 | 14, 15 | Changing qty 50→100 on the package line doesn't update dish quantities; **Reload Sets should follow the changed line qty**, not "No. of Guests" | `sale_order.py` | **DONE** `b6fe2c5` — `_lcs_effective_pax` makes a sized container authoritative; dishes resize on save (draft/sent). Qty formula extracted to `_lcs_set_line_qty` so expansion and resize can't drift. |
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
| C24a | 24 | Dish Overview: **food items only** (hide Delivery / Waiter Service) | `event_order_line.py` | **DONE** `07335b4` — stored `is_food_item` (non-storable goods only), removable default filter. Live split is 197 food / 6,907 not: 6,872 of the excluded are the single `Catering Service (Historical)` placeholder from the 2024 EO import, the rest are fees, delivery, waiter service and set containers. Correct, but it means the historical EOs carry no dish detail. |
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

### Verified on the live DB (26 Aug 2026)

- Batch 1 upgraded cleanly on `LaCasa_Odoo19` — both migrations ran, no errors.
- C17: 0 SO section lines still named "Hardware".
- C12: 0 💡 notes left on draft/sent orders; confirmed orders keep theirs by design.
- C24: 197 EO lines flagged as food, 193 carrying a category.
- C07 turned out to be already done (see above).

- **27 Aug 2026 — Batch 2 (set / pricing logic), deployed.** C11, C13, C14.
  `lcs_product_catalog` 19.0.2.19.0 → 19.0.2.21.0. Verified end-to-end through
  `odoo shell` against `LaCasa_Odoo19` (rolled back, nothing persisted):
  container prices at `100 × $398 = $39,800` with no orphan Package Fee section;
  62/62 dish lines carry `set_section`; confirm blocks on 0-of-3 picks and
  clears once minimums are met; 61 dish lines resize on a 100 → 60 change;
  Grand Opening stays at `1 × $16,388` and Cocktail Party keeps its 4 tiers.
  Migration back-fills: 7 package-fee flags, 27/27 rule sections, 2,721
  `set_section` values, 0 missing.

#### Bug found during batch 2 (pre-existing)

`set_western_buffet.min_guest_count` was **0** on the live database though its
data file declares **50** — the set data is `noupdate="1"`, so a minimum added
to the XML after the record existed never landed. Chinese Buffet, the
otherwise-identical set, had 50. The Western Buffet's "minimum order 50 pax",
printed in its own customer-facing recommendation, was silently ignored: a
30-guest order was sized and priced for 30. Fixed in 19.0.2.21.0.

> **Worth telling the client:** Western Buffet quotations under 50 guests will
> now floor to 50 pax. That is what the set has always claimed and what Chinese
> Buffet already did, but it is a visible price change on small orders.

- **27 Aug 2026 — C05a + C05b, deployed.** `lcs_crm_catering` 19.0.1.77.0.
  Both dropdowns now read exactly as slide 5 specifies. Verified against
  `ir_model_fields_selection` on the live DB: 15/15 service types and 6/6
  delivery types, in the client's order.

  Approach: **keys were preserved wherever the concept survives**, so 5,500+
  historical Sales Orders and Event Orders keep their classification and only
  the label and position change (`buffet` → "Event – Buffet", `utensil` →
  "Utensil Rental", `waiter_service` → "Staffing", …). Only the two values the
  client dropped moved: `sit_down_menu` (31 orders, 27 already
  `delivery_type='event'`) and `event` (2 legacy 2024 placeholders) → the new
  `event_banquet`, by **pre**-migration, since rows must stop referencing a
  value before Odoo reconciles the selection list on upgrade.

  Two notes for the client:
  - The deck writes "Event – Buffet" / "Event – Cocktail" with an en dash but
    "Event - Banquet" with a hyphen. Normalised to en dash throughout.
  - **38 of the 110 `buffet` orders are drop-offs**, not events, so they now
    read "Event – Buffet" with a drop-off delivery type. The client's list has
    no plain "Buffet", so this follows their taxonomy — worth confirming that a
    dropped-off buffet should not instead be "Party Food".

### Open decisions blocking further work

1. **C19** — which print format survives? There are three today (LCS Quotation,
   PDF Quote, Quotation/Order). The client asks whether to modify the standard one
   instead of maintaining separate LCS templates.
2. **C21a** — should sales be able to save their own package templates, and are
   those private to the salesperson or shared across the team?
3. **C21c** — what discount % triggers manager approval, and which group approves?
4. **C26b/c/d** — the checklist, delivery-assignment and waiter-assignment flows.
   The deck itself defers these to a meeting ("need to check with Prina").
5. **C26a** — buildable except for one input: there is no kitchen / production
   location list in the system, and the worksheet spec asks for "Kitchen assigned".

All of the above are written up as questions for the client in
[client_questions_open_items.md](client_questions_open_items.md).
