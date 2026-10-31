
titles_and_abbreviations = [
    "Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Rev.", "St.",
    "Ph.D.", "Phd.", "PhD.", "M.D.", "B.A.", "M.A.", "D.D.S.", "J.D.",
    "Co.", "Corp.", "Ave.", "Blvd.", "Rd.", "Mt.",
    "a.m.", "p.m.", "Jr.", "Sr.",
    "Gov.", "Gen.", "Capt.", "Lt.", "Maj.", "Col.", "Adm.", "Cmdr.",
    "Sgt.", "Cpl.", "Pvt.", "U.S.", "U.K.", "vs.", "i.e.", "e.g.",
    "Vol.", "Art.", "Sec.", "Chap.", "Fig.", "Ref.", "Dept.",
    "Sen.", "Rep.", "Pres.", "Hon.", "Supt.", "Insp.", "Atty.", "Amb.",
    "Fr.", "Mx.", "Messrs.", "Esq.", "Mgr.",
    "Bros.", "Assn.", "Assoc.", "Univ.",
    "Hwy.", "Pkwy.", "Bldg.", "Ln.", "Ct.", "Cir.", "Ste.",
]

# Words that also end sentences, such as "no." or "max.", do not belong here.
reference_abbreviations = [
    "approx.", "Approx.", "fig.", "figs.", "Figs.", "eq.", "Eq.", "eqs.", "Eqs.",
    "ref.", "refs.", "Refs.", "vol.", "vols.", "Vols.", "sec.", "secs.",
    "pp.", "cf.", "Cf.", "viz.", "ibid.", "Ibid.", "incl.", "Incl.",
    "dept.", "al.",
]

dates_and_times = [
    "Jan.", "Feb.", "Mar.", "Apr.", "Jun.", "Jul.", "Aug.",
    "Sep.", "Sept.", "Oct.", "Nov.", "Dec.",
    "Mon.", "Tue.", "Tues.", "Wed.", "Thu.", "Thur.", "Thurs.", "Fri.", "Sat.", "Sun.",
]

financial_abbreviations = [
    "Inc.", "Ltd.", "Corp.", "PLC.", "LLC.", "LLP.",
    "P/E.", "EPS.", "NAV.", "ROI.", "ROA.", "ROE.",
]

country_abbreviations = [
    "U.S.A.", "U.K.", "U.A.E.", "P.R.C.", "D.R.C.", "R.O.C.", 
    "E.U.", "U.N.", "A.U.",
    "U.S.", "U.K.", "E.U.", "P.R.C.", "D.R.C.", "R.O.C.",
]

DELIMITER_IGNORE_PREFIXES = set(
    titles_and_abbreviations + reference_abbreviations + dates_and_times +
    financial_abbreviations + country_abbreviations
)


