/** @odoo-module **/

import core from 'web.core';
import framework from 'web.framework';
import stock_report_generic from 'stock.stock_report_generic';

var QWeb = core.qweb;
var _t = core._t;

var MrpMoBomReport = stock_report_generic.extend({
    events: {
    },
    get_html: function() {
        var self = this;
        console.log("js loaded",this.given_context.active_id)
        var args = [
            this.given_context.active_id,
            this.given_context.searchQty || false,
            this.given_context.searchVariant,
        ];
        return this._rpc({
                model: 'report.bom_structure_in_mo',
                method: 'get_html',
                args: args,
                context: this.given_context,
            })
            .then(function (result) {
                self.data = result;
                if (! self.given_context.searchVariant) {
                    self.given_context.searchVariant = result.is_variant_applied && Object.keys(result.variants)[0];
                }
            });
    },
    set_html: function() {
        var self = this;
        console.log('set_worked')
        return this._super().then(function () {
            self.$('.o_content').html(self.data.lines);
        });
    },
    get_bom: function(event) {
      var self = this;
      var $parent = $(event.currentTarget).closest('tr');
      var activeID = $parent.data('id');
      console.log('get bom',$parent.data('id'))
      var productID = $parent.data('product_id');
      var lineID = $parent.data('line');
      var qty = $parent.data('qty');
      var level = $parent.data('level') || 0;
      return this._rpc({
              model: 'report.bom_structure_in_mo',
              method: 'get_bom',
              args: [
                  activeID,
                  productID,
                  parseFloat(qty),
                  lineID,
                  level + 1,
              ]
          })
          .then(function (result) {
              self.render_html(event, $parent, result);
          });
    },
    get_operations: function(event) {
      var self = this;
      var $parent = $(event.currentTarget).closest('tr');
      var activeID = $parent.data('bom-id');
      var qty = $parent.data('qty');
      var productId = $parent.data('product_id');
      var level = $parent.data('level') || 0;
      return this._rpc({
              model: 'report.bom_structure_in_mo',
              method: 'get_operations',
              args: [
                  productId,
                  activeID,
                  parseFloat(qty),
                  level + 1
              ]
          })
          .then(function (result) {
              self.render_html(event, $parent, result);
          });
    },
});

core.action_registry.add('bom_structure_in_mo', MrpMoBomReport);
export default MrpMoBomReport;
