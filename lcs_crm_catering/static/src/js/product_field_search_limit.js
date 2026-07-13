/** @odoo-module **/
/*
 * Limit the SO product-line autocomplete to 2 suggestions so "Search more…"
 * surfaces immediately.
 *
 * v19 drops the field-level `searchLimit` twice on the way to Many2XAutocomplete:
 *   1. ProductNameAndDescriptionField.m2oProps  → computeM2OProps() drops it
 *   2. Many2One.many2XAutocompleteProps         → getter omits it
 * So we plumb it through both, add it to Many2One's prop schema, and only
 * then does saleOrderLineProductField.extractProps'ing `searchLimit: 2` take
 * effect.
 */
import { patch } from "@web/core/utils/patch";
import { Many2One } from "@web/views/fields/many2one/many2one";
import { ProductNameAndDescriptionField }
    from "@product/product_name_and_description/product_name_and_description";
import { saleOrderLineProductField } from "@sale/js/sale_product_field";

// (1) Let Many2One accept the prop without OWL validation errors.
Many2One.props.searchLimit = { type: Number, optional: true };

// (2) Plumb it from Many2One → Many2XAutocomplete.
patch(Many2One.prototype, {
    get many2XAutocompleteProps() {
        const props = super.many2XAutocompleteProps;
        if (this.props.searchLimit !== undefined) {
            props.searchLimit = this.props.searchLimit;
        }
        return props;
    },
});

// (3) Plumb it from ProductNameAndDescriptionField → Many2One (m2oProps).
patch(ProductNameAndDescriptionField.prototype, {
    get m2oProps() {
        const p = super.m2oProps;
        if (this.props.searchLimit !== undefined) {
            p.searchLimit = this.props.searchLimit;
        }
        return p;
    },
});

// (4) Inject searchLimit=2 into SO product-line field props.
const _origExtractProps = saleOrderLineProductField.extractProps;
saleOrderLineProductField.extractProps = function (fieldInfo, dynamicInfo) {
    const props = _origExtractProps.call(this, fieldInfo, dynamicInfo);
    props.searchLimit = 2;
    return props;
};
