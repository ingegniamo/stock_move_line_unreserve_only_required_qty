Unreserve only required qty on move line
===============================
Now odoo has an issue.
Example:
Inventory quantity 4
Reserved quantity 3
Available quantity 1
If i confirm a stock move of 2 pieces, it will unreserve ALL the stock moves of the product until the quantity of "2" is reached.

With this module

It will unreserve only the pieces that are required minus the available quantity not reserved , in this case 2 (new stock move) - 1 (available quantity) = 1



NON RICHIESTO SE VIENE MERGIATA QUESTA PR https://github.com/odoo/odoo/pull/119999
Authors
~~~~~~~

* STeSI s.r.l

Contributors
~~~~~~~~~~~~

* Michele <dicroce.mf@stesi.eu>
