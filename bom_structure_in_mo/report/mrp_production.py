from odoo import models, api
from odoo.tools import float_round


class MrpProduction(models.AbstractModel):
    _name = 'report.bom_structure_in_mo'

    @api.model
    def get_mo_bom_data(self, mo_id):
        return mo_id

    @api.model
    def get_html(self, bom_id=False, searchQty=1, searchVariant=False):
        res = self._get_report_data(bom_id=bom_id, searchQty=searchQty,
                                    searchVariant=searchVariant)
        res['lines']['report_type'] = 'html'
        res['lines']['report_structure'] = 'all'
        res['lines']['has_attachments'] = res['lines']['attachments'] or any(
            component['attachments'] for component in
            res['lines']['components'])
        res['lines'] = self.env.ref('bom_structure_in_mo.MoBom')._render(
            {'data': res['lines']})
        return res

    @api.model
    def _get_report_data(self, bom_id, searchQty=0, searchVariant=False):
        lines = {}
        mo = self.env['mrp.production'].browse(bom_id)
        bom = mo.bom_id
        bom_quantity = searchQty or bom.product_qty or 1
        bom_product_variants = {}
        bom_uom_name = ''

        if bom:
            bom_uom_name = bom.product_uom_id.name

            # Get variants used for search
            if not bom.product_id:
                for variant in bom.product_tmpl_id.product_variant_ids:
                    bom_product_variants[variant.id] = variant.display_name

        lines = self._get_bom(bom.id, product_id=searchVariant,
                              line_qty=bom_quantity, level=1)

        return {
            'lines': lines,
            'variants': bom_product_variants,
            'bom_uom_name': bom_uom_name,
            'bom_qty': bom_quantity,
            'is_variant_applied': self.env.user.user_has_groups(
                'product.group_product_variant') and len(
                bom_product_variants) > 1,
            'is_uom_applied': self.env.user.user_has_groups('uom.group_uom'),
            'extra_column_count': 0
        }

    def _get_bom(self, bom_id=False, product_id=False, line_qty=False,
                 line_id=False, level=False):
        bom = self.env['mrp.bom'].browse(bom_id)
        company = bom.company_id or self.env.company
        bom_quantity = line_qty
        if line_id:
            current_line = self.env['mrp.bom.line'].browse(int(line_id))
            bom_quantity = current_line.product_uom_id._compute_quantity(
                line_qty, bom.product_uom_id) or 0
        # Display bom components for current selected product variant
        if product_id:
            product = self.env['product.product'].browse(int(product_id))
        else:
            product = bom.product_id or bom.product_tmpl_id.product_variant_id
        if product:
            attachments = self.env['mrp.document'].search(
                ['|', '&', ('res_model', '=', 'product.product'),
                 ('res_id', '=', product.id), '&',
                 ('res_model', '=', 'product.template'),
                 ('res_id', '=', product.product_tmpl_id.id)])
        else:
            # Use the product template instead of the variant
            product = bom.product_tmpl_id
            attachments = self.env['mrp.document'].search(
                [('res_model', '=', 'product.template'),
                 ('res_id', '=', product.id)])
        operations = self._get_operation_line(product, bom,
                                              float_round(bom_quantity,
                                                          precision_rounding=1,
                                                          rounding_method='UP'),
                                              0)
        lines = {
            'bom': bom,
            'bom_qty': bom_quantity,
            'bom_prod_name': product.display_name,
            'currency': company.currency_id,
            'product': product,
            'code': bom and bom.display_name or '',
            'price': product.uom_id._compute_price(
                product.with_company(company).standard_price,
                bom.product_uom_id) * bom_quantity,
            'total': sum([op['total'] for op in operations]),
            'level': level or 0,
            'operations': operations,
            'operations_cost': sum([op['total'] for op in operations]),
            'attachments': attachments,
            'operations_time': sum(
                [op['duration_expected'] for op in operations])
        }
        components, total = self._get_bom_lines(bom, bom_quantity, product,
                                                line_id, level)
        lines['total'] += total
        lines['components'] = components
        byproducts, byproduct_cost_portion = self._get_byproducts_lines(bom,
                                                                        bom_quantity,
                                                                        level,
                                                                        lines[
                                                                            'total'])
        lines['byproducts'] = byproducts
        lines['cost_share'] = float_round(1 - byproduct_cost_portion,
                                          precision_rounding=0.0001)
        lines['bom_cost'] = lines['total'] * lines['cost_share']
        lines['byproducts_cost'] = sum(
            byproduct['bom_cost'] for byproduct in byproducts)
        lines['byproducts_total'] = sum(
            byproduct['product_qty'] for byproduct in byproducts)
        lines['extra_column_count'] = 0
        return lines

    def _get_bom_lines(self, bom, bom_quantity, product, line_id, level):
        components = []
        total = 0
        for line in bom.bom_line_ids:
            line_quantity = (bom_quantity / (
                    bom.product_qty or 1.0)) * line.product_qty
            if line._skip_bom_line(product):
                continue
            company = bom.company_id or self.env.company
            price = line.product_id.uom_id._compute_price(
                line.product_id.with_company(company).standard_price,
                line.product_uom_id) * line_quantity
            if line.child_bom_id:
                factor = line.product_uom_id._compute_quantity(line_quantity,
                                                               line.child_bom_id.product_uom_id)
                sub_total = self._get_price(line.child_bom_id, factor,
                                            line.product_id)
                byproduct_cost_share = sum(
                    line.child_bom_id.byproduct_ids.mapped('cost_share'))
                if byproduct_cost_share:
                    sub_total *= float_round(1 - byproduct_cost_share / 100,
                                             precision_rounding=0.0001)
            else:
                sub_total = price
            sub_total = self.env.company.currency_id.round(sub_total)
            components.append({
                'prod_id': line.product_id.id,
                'prod_name': line.product_id.display_name,
                'code': line.child_bom_id and line.child_bom_id.display_name or '',
                'prod_qty': line_quantity,
                'prod_uom': line.product_uom_id.name,
                'prod_cost': company.currency_id.round(price),
                'parent_id': bom.id,
                'line_id': line.id,
                'level': level or 0,
                'total': sub_total,
                'child_bom': line.child_bom_id.id,
                'phantom_bom': line.child_bom_id and line.child_bom_id.type == 'phantom' or False,
                'attachments': self.env['mrp.document'].search(['|', '&',
                                                                ('res_model',
                                                                 '=',
                                                                 'product.product'),
                                                                ('res_id', '=',
                                                                 line.product_id.id),
                                                                '&', (
                                                                    'res_model',
                                                                    '=',
                                                                    'product.template'),
                                                                ('res_id', '=',
                                                                 line.product_id.product_tmpl_id.id)]),

            })
            total += sub_total
        return components, total

    def _get_byproducts_lines(self, bom, bom_quantity, level, total):
        byproducts = []
        byproduct_cost_portion = 0
        company = bom.company_id or self.env.company
        for byproduct in bom.byproduct_ids:
            line_quantity = (bom_quantity / (
                    bom.product_qty or 1.0)) * byproduct.product_qty
            cost_share = byproduct.cost_share / 100
            byproduct_cost_portion += cost_share
            price = byproduct.product_id.uom_id._compute_price(
                byproduct.product_id.with_company(company).standard_price,
                byproduct.product_uom_id) * line_quantity
            byproducts.append({
                'product_id': byproduct.product_id,
                'product_name': byproduct.product_id.display_name,
                'product_qty': line_quantity,
                'product_uom': byproduct.product_uom_id.name,
                'product_cost': company.currency_id.round(price),
                'parent_id': bom.id,
                'level': level or 0,
                'bom_cost': company.currency_id.round(total * cost_share),
                'cost_share': cost_share,
            })
        return byproducts, byproduct_cost_portion

    def _get_operation_line(self, product, bom, qty, level):
        operations = []
        total = 0.0
        qty = bom.product_uom_id._compute_quantity(qty,
                                                   bom.product_tmpl_id.uom_id)
        for operation in bom.operation_ids:
            if operation._skip_operation_line(product):
                continue
            operation_cycle = float_round(
                qty / operation.workcenter_id.capacity, precision_rounding=1,
                rounding_method='UP')
            duration_expected = (
                                        operation_cycle * operation.time_cycle * 100.0 / operation.workcenter_id.time_efficiency) + (
                                        operation.workcenter_id.time_stop + operation.workcenter_id.time_start)
            total = ((
                             duration_expected / 60.0) * operation.workcenter_id.costs_hour)
            operations.append({
                'level': level or 0,
                'operation': operation,
                'name': operation.name + ' - ' + operation.workcenter_id.name,
                'duration_expected': duration_expected,
                'total': self.env.company.currency_id.round(total),
            })
        return operations

    def _get_price(self, bom, factor, product):
        price = 0
        if bom.operation_ids:
            # routing are defined on a BoM and don't have a concept of quantity.
            # It means that the operation time are defined for the quantity on
            # the BoM (the user produces a batch of products). E.g the user
            # product a batch of 10 units with a 5 minutes operation, the time
            # will be the 5 for a quantity between 1-10, then doubled for
            # 11-20,...
            operation_cycle = float_round(factor, precision_rounding=1,
                                          rounding_method='UP')
            operations = self._get_operation_line(product, bom, operation_cycle,
                                                  0)
            price += sum([op['total'] for op in operations])

        for line in bom.bom_line_ids:
            if line._skip_bom_line(product):
                continue
            if line.child_bom_id:
                qty = line.product_uom_id._compute_quantity(
                    line.product_qty * (factor / bom.product_qty),
                    line.child_bom_id.product_uom_id)
                sub_price = self._get_price(line.child_bom_id, qty,
                                            line.product_id)
                byproduct_cost_share = sum(
                    line.child_bom_id.byproduct_ids.mapped('cost_share'))
                if byproduct_cost_share:
                    sub_price *= float_round(1 - byproduct_cost_share / 100,
                                             precision_rounding=0.0001)
                price += sub_price
            else:
                prod_qty = line.product_qty * factor / bom.product_qty
                company = bom.company_id or self.env.company
                not_rounded_price = line.product_id.uom_id._compute_price(
                    line.product_id.with_company(company).standard_price,
                    line.product_uom_id) * prod_qty
                price += company.currency_id.round(not_rounded_price)
        return price
