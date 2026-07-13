/** @odoo-module **/
/*
 * Limit the SO product-line autocomplete to 2 suggestions so "Search more…"
 * surfaces immediately. Patches sol_product_many2one's extractProps to inject
 * searchLimit; preserves all other behavior (variant handling, section/note,
 * translated name, etc.).
 */
import { saleOrderLineProductField } from "@sale/js/sale_product_field";

const _origExtractProps = saleOrderLineProductField.extractProps;
saleOrderLineProductField.extractProps = function (fieldInfo, dynamicInfo) {
    const props = _origExtractProps.call(this, fieldInfo, dynamicInfo);
    props.searchLimit = 2;
    return props;
};
