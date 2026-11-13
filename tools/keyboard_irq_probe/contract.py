"""Preserve terminal capture failure when canonical assets cannot be rechecked."""
from original_capture_contract import read_canonical_assets


def finalize_assets(root, expected, report):
    try:
        report['canonical_assets_unchanged'] = read_canonical_assets(root) == expected
    except (OSError, ValueError) as error:
        report.update(canonical_assets_unchanged=False, canonical_asset_check_error=repr(error))
    if not report['canonical_assets_unchanged']:
        report.update(status='failed', passed=False)


def require_success(report):
    if (report.get('status') != 'observed' or report.get('passed') is not True or
            report.get('canonical_assets_unchanged') is not True or report.get('child_exit_code') != 0):
        raise RuntimeError('Original keyboard capture failed; terminal report retained')
