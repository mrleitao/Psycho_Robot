"""Check the statistics printed in each paper against each other.

Every input below is a number printed in the paper (the table or page is named). The script recomputes the number
that the other printed values imply and reports whether the printed one matches. It needs no raw data.
Output: src/data/papers/consistency.json
"""
import json, math
from scipy import stats

out = []

def add(paper, where, what, printed, implied, tol, note=''):
    ok = bool(abs(printed - implied) <= tol)
    out.append(dict(paper=paper, where=where, what=what, printed=printed, implied=round(implied, 3), ok=ok, note=note))

def d_from_t(t, df):  # the 2t / sqrt(df) formula the papers use
    return 2 * t / math.sqrt(df)

def eta_from_F(F, df1, df2):
    return F * df1 / (F * df1 + df2)

# ---- Generative AI paper (Logg, Leitao, Ulu): Welch t tests, d from t and df
G = 'Generative AI preprint'
for tbl, lab, t, df, d in [
    ('Table 11', 'Exp 1 productivity, drafter vs editor', 2.09, 598.12, .17),
    ('Table 13', 'Exp 1 time, drafter vs editor', -2.69, 598.81, -.22),
    ('Table 14', 'Exp 1 control, drafter vs editor', -4.62, 579.26, -.38),
    ('Table 15', 'Exp 1 responsibility, drafter vs editor', -5.07, 584.93, -.42),
    ('Table 16', 'Exp 1 creativity, drafter vs editor', -9.60, 558.64, -.81),
    ('Table 20', 'Exp 2 productivity, drafter vs editor', -0.65, 377.50, -.23),
    ('Table 20', 'Exp 2 productivity, control vs editor', -3.13, 385.43, -.32),
    ('Table 20', 'Exp 2 productivity, control vs drafter', -2.82, 485.98, -.26),
    ('Table 22', 'Exp 2 judge score, drafter vs editor', -2.46, 458.09, -.23),
    ('Table 22', 'Exp 2 judge score, control vs editor', -7.10, 405.43, -.70),
    ('Table 22', 'Exp 2 judge score, control vs drafter', -4.33, 505.86, -.39),
    ('Table 24', 'Exp 2 time, drafter vs editor', -0.21, 366.85, -.02),
    ('Table 24', 'Exp 2 time, control vs editor', 1.55, 378.54, -.70),
    ('Table 24', 'Exp 2 time, control vs drafter', 2.02, 489.76, .18),
    ('Table 25', 'Exp 2 control, drafter vs editor', -0.70, 429.65, -.07),
    ('Table 25', 'Exp 2 control, control vs editor', 6.51, 337.87, .71),
    ('Table 25', 'Exp 2 control, control vs drafter', 7.51, 501.65, .67),
    ('Table 26', 'Exp 2 responsibility, drafter vs editor', -3.91, 443.13, -.37),
    ('Table 26', 'Exp 2 responsibility, control vs editor', 5.91, 329.37, .65),
    ('Table 26', 'Exp 2 responsibility, control vs drafter', 10.37, 483.20, .94),
    ('Table 27', 'Exp 2 creativity, drafter vs editor', -7.89, 436.50, -.75),
    ('Table 27', 'Exp 2 creativity, control vs editor', 1.61, 337.83, .18),
    ('Table 27', 'Exp 2 creativity, control vs drafter', 10.72, 496.54, .96),
    ('Table 29', 'Exp 2 write time, control vs editor', 4.38, 335.39, .48),
    ('Table 30', 'Exp 2 frustration, drafter vs editor', 0.44, 344.35, .05),
]:
    add(G, tbl, f'Cohen d from t and df: {lab}', d, d_from_t(t, df), 0.03)

# a printed mean difference should equal the difference of the printed means
add(G, 'Table 27', 'Exp 2 creativity, control minus drafter (difference column)', 119.63, 78.01 - 58.39, 0.05,
    'The printed means (78.01 and 58.39) and the interval [16.03; 23.22] both imply about 19.6.')
add(G, 'Table 25', 'Exp 2 control, control minus editor', 10.11, 86.00 - 75.89, 0.02)
add(G, 'Table 26', 'Exp 2 responsibility, control minus drafter', 17.29, 88.20 - 70.91, 0.02)
# the regression coefficient the text calls the expertise effect on control
b, se = 5.44, 2.03
add(G, 'Results text and Table 3', 'Exp 1 expertise effect on control: t', -3.64, b / se, 0.1,
    'The text prints t(595) = -3.64 and beta = -0.14 for expertise; those are the drafter values. Table 3 gives b = 5.44, SE = 2.03.')
# paired d
add(G, 'Table 21', 'Exp 2 editor, judge score change: paired d from t and n=178', .53, 6.99 / math.sqrt(178), 0.02)

# ---- Parasocial paper: Table 2 relative weights sum to R-squared, and F follows from R-squared
P = 'Parasocial paper'
rw = {  # trait: (parts, total R2, F)
    'Need for humor': ([.097, .014, .005, .011, .005, .001], .133, 21.022),
    'Generosity': ([.026, .051, .005, .012, .026, .002], .124, 19.457),
    'Loyalty': ([.008, .003, .024, .020, .008, .001], .063, 9.164),
    'Honesty': ([.001, .001, 0.0, .007, .011, .002], .022, 3.037),
    'Kindness': ([.020, .028, .007, .003, .086, .004], .148, 23.889),
    'Friendship': ([.037, .004, .010, .003, .015, 0.0], .069, 10.109),
}
for trait, (parts, r2, F) in rw.items():
    add(P, 'Table 2', f'Relative weights sum to total R2: {trait}', r2, sum(parts), 0.003)
    for df2, tag in ((822, 'N = 829, so df = 6 and 822'),):
        f_imp = (r2 / 6) / ((1 - r2) / df2)
        add(P, 'Table 2', f'F from R2 with {tag}: {trait}', F, f_imp, max(0.12, 0.012 * F))

# ---- Mega-analysis: t from b and SE, and d from t
M = 'Mega-analysis'
for lab, b, se, t in [('Model 3, phone', -.241, .065, -3.713), ('Model 3 interaction', -.313, .103, -3.03),
                      ('men, simple effect', -.461, .098, -4.706), ('women, simple effect', -.148, .072, -2.046)]:
    add(M, 'Results text', f't from b and SE: {lab}', t, b / se, 0.08)
add(M, 'Results text', 'd from t(1685) = -3.713 (2t / sqrt df)', -.181, d_from_t(-3.713, 1685), 0.01)
add(M, 'Results text', 'd from t(1684) = -3.03 (2t / sqrt df)', -.148, d_from_t(-3.03, 1684), 0.01)
add(M, 'Table 1', 'Study sizes add to the stated total of 1,778', 1778, 98 + 189 + 217 + 191 + 305 + 271 + 130 + 143 + 234, 0)

# ---- VR buffet paper: partial eta squared from F (df 1 and 26 for N = 28; 1 and 27 for N = 29)
V = 'VR buffet paper'
for lab, F, eta, df2 in [('Liking, drug', 4.375, .144, 26), ('Typicality, drug', 8.381, .244, 26), ('Satisfaction, drug', 4.680, .153, 26),
                         ('Presence, drug x order', 10.697, .291, 26), ('Time to first selection, drug x order', 7.799, .224, 27),
                         ('Time to first selection, order', 4.339, .138, 27)]:
    add(V, 'Tables 1 and 2', f'partial eta squared from F: {lab}', eta, eta_from_F(F, 1, df2), 0.003)

# ---- Thesis: p values from the printed tests
T = "Master's thesis"
add(T, 'Results', 'p for F(2, 302) = 1.31', .269, stats.f.sf(1.31, 2, 302), 0.005)
for lab, t, df, p in [('human vs both computers', 1.549, 302, .123), ('human vs basic computer', 1.093, 302, .275),
                      ('human vs sophisticated computer', 1.585, 302, .114), ('sophisticated vs basic', -0.490, 302, .625)]:
    add(T, 'Results', f'p for t({df}) = {t}: {lab}', p, 2 * stats.t.sf(abs(t), df), 0.003)

json.dump(dict(generated_by='analysis/papers_consistency.py', rows=out), open('src/data/papers/consistency.json', 'w'), indent=1)
bad = [o for o in out if not o['ok']]
print(len(out), 'checks;', len(bad), 'do not match')
for o in bad: print(' -', o['paper'], '|', o['where'], '|', o['what'], '| printed', o['printed'], 'implied', o['implied'])
