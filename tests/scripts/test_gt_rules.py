import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts")))

import gt_rules


def test_ions_classified():
    assert gt_rules.gt_class_for("BHPQYMZQTOCNFJ-UHFFFAOYSA-N") == "ion"
    assert gt_rules.gt_class_for("JLVVSXFLKOJNIY-UHFFFAOYSA-N") == "ion"
    assert gt_rules.gt_class_for("PXHVJJICTQNCMI-UHFFFAOYSA-N") == "ion"
    assert gt_rules.gt_class_for("VEXZGXHMUGYJMC-UHFFFAOYSA-M") == "ion"


def test_ion_element_correct():
    assert gt_rules.ion_element("BHPQYMZQTOCNFJ-UHFFFAOYSA-N") == "Ca"
    assert gt_rules.ion_element("JLVVSXFLKOJNIY-UHFFFAOYSA-N") == "Mg"
    assert gt_rules.ion_element("PTFCDOFLOPIGGS-UHFFFAOYSA-N") == "Zn"


def test_organic_stays_organic():
    assert gt_rules.gt_class_for("LFQSCWFLJHTTHZ-UHFFFAOYSA-N") == "organic"
    assert gt_rules.gt_class_for("QJFSABGVXDWMIW-UHFFFAOYSA-N") == "organic"
