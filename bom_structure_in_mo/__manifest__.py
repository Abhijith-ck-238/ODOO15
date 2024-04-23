{
    'name': 'BOM Structure In MO',
    'version': '17.0.1.0.0',
    'depends': ['base', 'mrp'],
    'author': 'ABD',
    'category': 'Human Resources',
    'description': "This module will add a smart button in Manufacture to "
                   "show the details of BOM",
    'data': [
        'views/bom_structure_in_mo.xml',
        'report/bom_struction_in_mo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bom_structure_in_mo/static/src/mo_bom_overview.js',
        ],
    }
}
