from collections import Counter, defaultdict

from odoo import _, api, fields, tools, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import OrderedSet
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _free_reservation(self, product_id, location_id, quantity, lot_id=None, package_id=None, owner_id=None,
                          ml_to_ignore=None):
        """ When editing a done move line or validating one with some forced quantities, it is
        possible to impact quants that were not reserved. It is therefore necessary to edit or
        unlink the move lines that reserved a quantity now unavailable.

        :param ml_to_ignore: recordset of `stock.move.line` that should NOT be unreserved
        """
        self.ensure_one()

        if ml_to_ignore is None:
            ml_to_ignore = self.env['stock.move.line']
        ml_to_ignore |= self

        # Check the available quantity, with the `strict` kw set to `True`. If the available
        # quantity is greather than the quantity now unavailable, there is nothing to do.
        available_quantity = self.env['stock.quant']._get_available_quantity(
            product_id, location_id, lot_id=lot_id, package_id=package_id, owner_id=owner_id, strict=True
        )
        if quantity > available_quantity:
            quantity = quantity - available_quantity
            # We now have to find the move lines that reserved our now unavailable quantity. We
            # take care to exclude ourselves and the move lines were work had already been done.
            outdated_move_lines_domain = [
                ('state', 'not in', ['done', 'cancel']),
                ('product_id', '=', product_id.id),
                ('lot_id', '=', lot_id.id if lot_id else False),
                ('location_id', '=', location_id.id),
                ('owner_id', '=', owner_id.id if owner_id else False),
                ('package_id', '=', package_id.id if package_id else False),
                ('product_qty', '>', 0.0),
                ('id', 'not in', ml_to_ignore.ids),
            ]
            # We take the current picking first, then the pickings with the latest scheduled date
            current_picking_first = lambda cand: (
                cand.picking_id != self.move_id.picking_id,
                -(cand.picking_id.scheduled_date or cand.move_id.date).timestamp()
                if cand.picking_id or cand.move_id
                else -cand.id,
            )
            outdated_candidates = self.env['stock.move.line'].search(outdated_move_lines_domain).sorted(
                current_picking_first)

            # As the move's state is not computed over the move lines, we'll have to manually
            # recompute the moves which we adapted their lines.
            move_to_recompute_state = self.env['stock.move']
            to_unlink_candidate_ids = set()

            rounding = self.product_uom_id.rounding
            for candidate in outdated_candidates:
                if float_compare(candidate.product_qty, quantity, precision_rounding=rounding) <= 0:
                    quantity -= candidate.product_qty
                    if candidate.qty_done:
                        move_to_recompute_state |= candidate.move_id
                        candidate.product_uom_qty = 0.0
                    else:
                        to_unlink_candidate_ids.add(candidate.id)
                    if float_is_zero(quantity, precision_rounding=rounding):
                        break
                else:
                    # split this move line and assign the new part to our extra move
                    quantity_split = float_round(
                        candidate.product_qty - quantity,
                        precision_rounding=self.product_uom_id.rounding,
                        rounding_method='UP')
                    candidate.product_uom_qty = self.product_id.uom_id._compute_quantity(quantity_split,
                                                                                         candidate.product_uom_id,
                                                                                         rounding_method='HALF-UP')
                    move_to_recompute_state |= candidate.move_id
                    break
            self.env['stock.move.line'].browse(to_unlink_candidate_ids).unlink()
            move_to_recompute_state._recompute_state()
