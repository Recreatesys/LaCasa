# Open questions for LCS — blocking items from the July 2026 deck

Six comments can't be built without a decision from the client. The deck itself
defers most of them ("will discuss this with you in more details during the
meeting", "need to check with Prina").

Each question below changes what gets built — none is a preference check.

---

## C19 — Too many preview & print formats (slide 19)

> *"Or should we modify the standard version? Seems now we have too many formats of preview & print version."*

The Print menu was already cut back to a single **LCS Quotation** (done, C18).
The mismatch that's left is between **Print** and **Preview**: Print produces the
LCS-branded PDF, while Preview opens the standard Odoo customer portal page —
different layout, different branding, and in the screenshot it still shows a
placeholder *"Your Logo"* and the phone number *+1 555-555-5556*.

1. **When sales clicks Preview, what should the customer see** — the LCS-branded
   quotation, identical to the PDF? Or is the Odoo portal page acceptable as-is?
2. **Is the customer portal part of your process at all?** If clients only ever
   receive the PDF by email, Preview can be removed from the button bar entirely,
   which is the cheapest way to end the confusion.
3. If the portal stays, **should it be LCS-branded** (logo, phone, colours)? That
   part is configuration — no development, we just need the correct assets.

---

## C21a — Sales-created package templates (slide 21)

> *"Possible to allow our sales to create their own package template or to use back their own saved package during the time they create package to our client?"*

1. **Private or shared?** Is a saved package visible only to the salesperson who
   created it, or to the whole sales team?
2. **What exactly gets saved** — just the dish selections, or also the negotiated
   prices and discounts on that quotation?
3. **Reusable for any customer, or tied to one?** "Save this for the next client"
   is a different feature from "reload what we quoted Manulife last year".
4. **Who can promote a personal template into an official set** that appears in
   the catalogue for everyone — a manager only, or anyone?
5. **What happens when the underlying dish prices change** after a template is
   saved — should reloading it use today's prices, or the prices as saved?

---

## C21c — Manager approval on discounted prices (slide 21)

> *"As we'll allow sales to revise the price or place discount to client, possible that we can set, if the price is lower to certain %, need to get approval from the manager?"*

1. **What is the threshold, and measured against what?** A % off the list price,
   or a minimum margin over cost? (Cost is now visible per line — C21b — so
   either is buildable.)
2. **One number for everything, or does it vary** by set, service type, or
   customer type (Corporate vs Partner)?
3. **Whole order, or per line?** A 40% discount on one dessert is not the same
   risk as 40% off the whole buffet.
4. **Who approves** — anyone in the Sales Manager group, or specific named people?
5. **What happens when it trips?** Block confirmation until a manager approves,
   or let it through and notify the manager afterwards?
6. **Does the approval need an audit trail** — who approved, when, and at what
   discount — for later review?

---

## C26b — Catering order checklist for CS (slide 26)

> *"Generate a catering order checklist for CS team (need to check with Prina)"*

1. **Can Prina share the checklist you use today** (the paper form or Excel)? That
   answers most of what follows in one go.
2. **One per Event Order, or one per day** covering every order that day?
3. **Printed to tick by hand, or ticked inside Odoo** — the second records who
   checked what and when, and can block dispatch until complete.
4. **When is it produced** — as soon as the EO is created, or a set number of days
   before the event?
5. **Does anything depend on it being finished** (e.g. the EO can't be marked ready
   until every item is ticked)?

---

## C26c — CS assigning delivery (slide 26)

> *"How to help our CS team to assign delivery for each order?"*

1. **Are drivers people or a list of names?** Today "Preferred Driver" is a fixed
   dropdown (阿源, 文仔, 恆哥, Lalamove, GoGoVan…). Should those become real
   records — so you can see one driver's whole day — or stay a simple list?
2. **Should the system stop a driver being double-booked** on the same date and
   time slot? Waiters already work this way, so the pattern exists.
3. **Do you need a dispatch board** — every delivery for a chosen day, grouped by
   driver, assignable by drag — or is setting the driver on each EO enough?
4. **What are the driver statuses?** Slide 26 asks for a "Driver status" column;
   we need the actual list (Assigned → Confirmed → Out → Delivered?).
5. **Does the driver need to see anything** — a printed run sheet for the day, or a
   login of their own?
6. **Who assigns** — the CS team only, or can sales set it too and CS overrides?
   (Slide 4 asks for exactly this: sales suggests, CS finalises.)

---

## C26d — Event team assigning waiters (slide 26)

> *"How to allow our event team to assign waiters in Event order portal?"*

This is the other half of C16 (*"This part should be input by operation team… for
sales, they need to show to client how many waiters their package includes"*).

1. **Confirming C16:** the named waiter roster moves off the quotation onto the
   Event Order, and sales sees only a count — *"includes 3 waiters (4 hrs)"* — is
   that right?
2. **Where do waiters come from?** HR employee records (as today), or a separate
   casual/part-time staff list that ops maintains?
3. **Should the no-double-booking rule carry over** to the Event Order?
4. **Who can assign** — a dedicated Event Team group, or anyone in operations?
5. **Per-waiter times, or just a headcount?** Today the quotation captures start
   and end time per person.

---

## C26a — Worksheets (slide 26) — one input needed before building

C26a itself is clear and doesn't need a decision, but one column does:

> *"Event: EO Ref / Customer / Event Date / Event Time / **Kitchen assigned** / Driver status / Waiter assigned / EO status"*

**What are the kitchens?** There is no kitchen or production-location list in the
system today. Please supply the names (and whether an order can be split across
more than one kitchen).
