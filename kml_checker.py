"""Exact KML zone-name checker. Python 3.9+, standard library only."""
import argparse
import difflib
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

# Edit this dictionary when the approved naming guide changes.
# Keys are exact zone names; values are the required upload zone types.
ZONE_TYPES = {
    '(A1-L) Main Left': 'Main Left',
    '(B1-L) Main Left Out': 'Main Left Out',
    '(A1-R) Main Right': 'Main Right',
    '(B1-R) Main Right Out': 'Main Right Out',
    '(A3) Front Drive Lane': 'Front Drive Lane',
    '(C1) Left Side': 'Left Side',
    '(C2) Right Side': 'Right Side',
    '(D1) Rear': 'Rear of Store',
    '(A2) Front Apron': 'Concrete',
    '(A2) Walkways/Sidewalks': 'Concrete',
    '(E1) Loading Dock/Truck Well': 'Concrete',
}
NS = {'k': 'http://www.opengis.net/kml/2.2'}


def suggest(name):
    """Suggest a name; never change the source file automatically."""
    normalized = ' '.join(name.split()).casefold()
    for approved in ZONE_TYPES:
        if normalized == approved.casefold():
            return approved
    # A3 Front Apron is ambiguous: code and description disagree.
    if normalized == '(a3) front apron':
        return '(A3) Front Drive Lane OR (A2) Front Apron — verify the area'
    candidates = difflib.get_close_matches(name, ZONE_TYPES, n=1, cutoff=0.45)
    return candidates[0] if candidates else 'Choose an approved name from the guide'


def check_kml(path):
    """Return a report dictionary; only Placemark names are checked."""
    path = Path(path)
    result = {'file': str(path), 'count': 0, 'issues': [], 'missing': [], 'error': None}
    try:
        root = ET.parse(path).getroot()
        # Also accept KML exports without an XML namespace.
        placemarks = root.findall('.//k:Placemark', NS)
        if root.tag == 'Placemark':
            placemarks = [root]
        elif not placemarks and not root.tag.startswith('{'):
            placemarks = root.findall('.//Placemark')
        if not placemarks:
            result['error'] = 'No KML Placemarks found; nothing could be checked.'
            return result
        seen = set()
        for index, placemark in enumerate(placemarks, 1):
            tag = 'k:name' if placemark.tag.startswith('{') else 'name'
            name = placemark.findtext(tag, default='', namespaces=NS)
            result['count'] += 1
            seen.add(name)
            if name not in ZONE_TYPES:
                result['issues'].append({'placemark': index, 'name': name,
                                         'suggestion': suggest(name) if name else 'Add an approved zone name'})
        result['missing'] = [name for name in ZONE_TYPES if name not in seen]
    except (OSError, ET.ParseError) as exc:
        result['error'] = str(exc)
    return result


def format_report(result):
    lines = [f"FILE: {result['file']}"]
    if result['error']:
        return '\n'.join(lines + ['ERROR: ' + result['error']])
    issues = result['issues']
    lines.append(f"{'PASS' if not issues else 'FIX NAMES'}: {result['count']} Placemarks checked; {len(issues)} naming issue(s).")
    for issue in issues:
        lines.extend([f"  Placemark #{issue['placemark']}: {issue['name']!r}",
                      f"    Suggested: {issue['suggestion']}"])
    if result['missing']:
        lines.append('REVIEW — absent exact names (may not apply to this site):')
        lines.extend('  ' + name for name in result['missing'])
    else:
        lines.append('All names in the guide are represented.')
    lines.append('Naming only: boundaries, dock coverage, and upload zone types are not verified.')
    return '\n'.join(lines)


def expand_paths(paths):
    files = []
    for item in paths:
        path = Path(item)
        if path.is_dir():
            files.extend(sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() == '.kml'))
        else:
            files.append(path)
    return list(dict.fromkeys(files))


def gui():
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
        from tkinter.scrolledtext import ScrolledText
        root = tk.Tk()
    except Exception as exc:
        print(f'Could not open the file picker: {exc}\nUse: python kml_checker.py "your-file.kml"', file=sys.stderr)
        return 2
    root.title('KML Zone Name Checker')
    root.geometry('950x650')
    tk.Label(root, text='KML Zone Name Checker', font=('Arial', 18, 'bold')).pack(pady=(15, 5))
    tk.Label(root, text='Exact names, including spaces and capitalization. Original KMLs are never edited.').pack()
    buttons = tk.Frame(root)
    buttons.pack(pady=12)
    output = ScrolledText(root, wrap='word', font=('Consolas', 11))
    output.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    def show(paths):
        files = expand_paths(paths)
        output.delete('1.0', 'end')
        if not files:
            output.insert('end', 'No KML files found in that folder.')
            return
        reports = [check_kml(p) for p in files]
        passed = sum(not r['error'] and not r['issues'] for r in reports)
        output.insert('end', f'{passed}/{len(reports)} files pass the naming check.\n\n')
        output.insert('end', '\n\n' + ('\n\n' + '-' * 60 + '\n\n').join(format_report(r) for r in reports))

    def select_files():
        paths = filedialog.askopenfilenames(title='Select KML files', filetypes=[('KML files', '*.kml'), ('All files', '*.*')])
        if paths:
            show(paths)

    def select_folder():
        path = filedialog.askdirectory(title='Select a folder containing KMLs')
        if path:
            show([path])

    def save_report():
        text = output.get('1.0', 'end-1c')
        if not text.strip():
            return
        path = filedialog.asksaveasfilename(defaultextension='.txt', filetypes=[('Text report', '*.txt')])
        if path:
            try:
                Path(path).write_text(text, encoding='utf-8')
            except OSError as exc:
                messagebox.showerror('Could not save', str(exc))

    for title, action in [('Select KML files', select_files), ('Select folder', select_folder), ('Save report', save_report)]:
        tk.Button(buttons, text=title, command=action, padx=12).pack(side='left', padx=5)
    root.mainloop()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='*', help='KML files or folders; omit to open the app')
    args = parser.parse_args()
    if not args.paths:
        return gui()
    files = expand_paths(args.paths)
    if not files:
        print('No KML files found.', file=sys.stderr)
        return 2
    reports = [check_kml(path) for path in files]
    print(('\n\n' + '-' * 60 + '\n\n').join(format_report(r) for r in reports))
    return 2 if any(r['error'] for r in reports) else 1 if any(r['issues'] for r in reports) else 0


if __name__ == '__main__':
    sys.exit(main())
