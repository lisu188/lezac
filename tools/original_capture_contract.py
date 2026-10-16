"""Canonical shipped inputs and private-display geometry for original captures."""
import configparser
import hashlib

ASSET_PINS = {
    'BOMOMIMK.SPR': (20168, '08dfd0e59ba191c52af2529bdfa140fd15a57829f0c6c13bbb78e156769ac0d1'),
    'BOMPAL.PAL': (768, 'f2559164074ca529ba6c275a9831b11c6da9e6317f09b3d9228c299d6f8f8319'),
    'CARO.CAR': (8450, '949cce4db6071d6675a291c978d725c6e4ee1730b2c7a428bc1c8a8185cbd8d8'),
    'ENGLISH.DOC': (3522, 'e2fd2f2521b0277f2fca0c8f2a265408412542932bb6e977bf1ab3d0aabdfed9'),
    'FONTS.SPR': (5425, 'f65aa9bbba2a66ee69f1b279a32c448e36012feb53441fbbb8e64e31bee87a0e'),
    'GRAN.MST': (399, '3f0cf17706d557ca863d6e39bfa6641fba777a88815ba3f0a22e5ac89e0e39e2'),
    'ITALIANO.DOC': (4392, '5ea7481d3179e60b6f1229aa114dc4b47c95f7c1200c7888ad5c259f161317c1'),
    'LEZAC.EXE': (52384, '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'),
    'LIVELS.SCH': (41047, 'd8b553871014108515d6af05b0853de8ccc22e4d3e44d63533ba1167fdc8c7b2'),
    'PROEFS.SON': (782, 'b5bc702a27ac85554cc76a62fced07567921b07d5c16f2027a62fbc956df701d'),
    'PROVA.SPR': (21250, 'd6d6b634f8613251f6e82e9a15c5c68e2be437892bfa25c53eb4bcd9094188b7'),
    'RECS.DAT': (92, '27197ebb56fb339e4d41baf6ad5282cd79bb66b642c81ae406e607a263c80eb8'),
    'SETUP.LOG': (566, '4c86cd7436be442663b10b1425bbcd7a179b7955b67c23632bf20a8180144a14'),
    'SFONLEF.ZBG': (34292, 'b1b7cc03122510318c1a3670f151712406e9e3fa60aabd8fb558320766c3835c'),
}


def read_canonical_assets(root):
    suffixes = {'.EXE', '.DAT', '.SPR', '.PAL', '.SCH', '.SON', '.MST', '.CAR', '.ZBG', '.DOC', '.LOG'}
    names = {path.name for path in root.iterdir() if path.is_file() and path.suffix.upper() in suffixes}
    if names != set(ASSET_PINS):
        raise ValueError('Canonical original asset domain differs')
    result = {}
    for name, (size, expected) in ASSET_PINS.items():
        with (root / name).open('rb') as stream:
            raw = stream.read(size + 1)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Canonical original asset differs: ' + name)
        result[name] = raw
    return result


def validate_geometry(stdout, window):
    if type(stdout) is not str or not 0 < len(stdout) <= 2048:
        raise ValueError('Capture geometry output differs')
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    try:
        parser.read_string('[geometry]\n' + stdout)
        if parser.defaults() or parser.sections() != ['geometry'] or set(parser['geometry']) != {
                'WINDOW', 'X', 'Y', 'WIDTH', 'HEIGHT', 'SCREEN'}:
            raise ValueError('Capture geometry output differs')
        values = {key: int(value) for key, value in parser['geometry'].items()}
        if any(str(values[key]) != value for key, value in parser['geometry'].items()):
            raise ValueError('Capture geometry output differs')
    except (configparser.Error, ValueError) as error:
        raise ValueError('Capture geometry output differs') from error
    if (str(values['WINDOW']) != window or values['WIDTH'] != 320 or values['HEIGHT'] != 200 or
            values['SCREEN'] != 0 or not 0 <= values['X'] <= 1024 - 320 or not 0 <= values['Y'] <= 768 - 200):
        raise ValueError('Capture geometry output differs')
    return values
