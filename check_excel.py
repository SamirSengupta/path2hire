import pandas as pd

# Load the Excel file
df = pd.read_excel('Sample Assessment questions.xlsx')

print("=" * 70)
print("EXCEL FILE DIAGNOSTIC REPORT")
print("=" * 70)

# Show basic info
print(f"\nTotal rows in Excel: {len(df)}")
print(f"Columns: {list(df.columns)}\n")

# Check which column has categories
cat_column = None
for possible in ['Categories', 'Categories/Attributes', 'Category']:
    if possible in df.columns:
        cat_column = possible
        print(f"✓ Found category column: '{cat_column}'\n")
        break

if not cat_column:
    print("❌ ERROR: No category column found!")
    exit()

# Show distribution
print("=" * 70)
print("QUESTION DISTRIBUTION BY CATEGORY")
print("=" * 70)

categories = df[cat_column].value_counts()
print(f"\n{'Category':<40} {'Count':>10}")
print("-" * 70)

total_valid = 0
for cat, count in categories.items():
    print(f"{str(cat):<40} {count:>10}")
    total_valid += count

print("-" * 70)
print(f"{'TOTAL':<40} {total_valid:>10}")

# Expected categories
EXPECTED = [
    'Accounting Knowledge',
    'Attention to Detail',
    'Business & Economic Acumen',
    'Communication Skills',
    'Compliance & Ethics',
    'Finacial Concepts Skill',
    'Personality Preference',
    'Problem Solving Skills',
    'Quantitative & Math Skill',
    'Tech & Tool Familiarity'
]

print("\n" + "=" * 70)
print("EXPECTED CATEGORIES STATUS")
print("=" * 70)
print(f"\n{'Category':<40} {'Status':>15} {'Count':>10}")
print("-" * 70)

missing = []
incomplete = []

for cat in EXPECTED:
    count = len(df[df[cat_column] == cat])
    if count == 0:
        status = "❌ MISSING"
        missing.append(cat)
    elif count < 10:
        status = "⚠️  INCOMPLETE"
        incomplete.append(cat)
    else:
        status = "✓ OK"
    print(f"{cat:<40} {status:>15} {count:>10}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

if missing:
    print(f"\n❌ Missing categories ({len(missing)}):")
    for cat in missing:
        print(f"   - {cat}")

if incomplete:
    print(f"\n⚠️  Incomplete categories ({len(incomplete)}) - need more questions:")
    for cat in incomplete:
        count = len(df[df[cat_column] == cat])
        needed = 10 - count
        print(f"   - {cat}: has {count}, needs {needed} more")

if not missing and not incomplete:
    print("\n✓ All categories have 10+ questions!")
    print("✓ Ready for 100-question assessment!")
else:
    total_needed = len(missing) * 10 + sum(10 - len(df[df[cat_column] == cat]) for cat in incomplete)
    print(f"\n📝 Total questions needed: {total_needed}")
    print(f"   Current: {total_valid} questions")
    print(f"   Target: 100 questions")

print("\n" + "=" * 70)