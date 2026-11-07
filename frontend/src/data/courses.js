export const COURSES = [
  {
    id: 'python',
    title: 'Python Mastery',
    tagline: 'Zero to automation',
    mark: 'PY',
    accent: 'bg-ember-500/15 text-ember-300 ring-ember-500/25',
    sections: [
      {
        id: 'py-s1',
        title: 'Python foundations',
        lessons: [
          { id: 'py-01', title: 'Why Python & how this course works', duration: '8 min', completed: true },
          { id: 'py-02', title: 'Variables, types & f-strings', duration: '12 min', completed: true },
          { id: 'py-03', title: 'Control flow that reads cleanly', duration: '14 min', completed: true },
        ],
      },
      {
        id: 'py-s2',
        title: 'Core Python · Module 02',
        lessons: [
          { id: 'py-04', title: 'Lists, dicts & comprehensions', duration: '17 min', completed: true },
          { id: 'py-05', title: 'Modules, packages & imports', duration: '16 min', completed: true },
          { id: 'py-06', title: 'Errors, exceptions & guards', duration: '15 min', completed: true },
          { id: 'py-07', title: 'Functions, Scope & Clean Code', duration: '18 min', completed: false },
        ],
      },
      {
        id: 'py-s3',
        title: 'Automation project',
        lessons: [
          { id: 'py-08', title: 'Files, paths & the standard library', duration: '20 min', completed: false },
          { id: 'py-09', title: 'Calling APIs with requests', duration: '22 min', completed: false },
          { id: 'py-10', title: 'Scheduling a daily automation', duration: '19 min', completed: false },
          { id: 'py-11', title: 'Testing your automation', duration: '18 min', completed: false },
          { id: 'py-12', title: 'Ship it: packaging & handoff', duration: '24 min', completed: false },
        ],
      },
    ],
    lesson: {
      id: 'py-07',
      module: 'Core Python · Module 02',
      title: 'Functions, Scope & Clean Code',
      duration: '18 min',
      filename: 'lesson_04_functions.py',
      language: 'Python',
      code: `def calculate_total(prices, tax_rate=0.14):
    """Sum the cart and apply tax."""
    subtotal = sum(prices)
    return round(subtotal * (1 + tax_rate), 2)

cart = [12.50, 8.00, 21.75]
print("Total:", calculate_total(cart))`,
      narration:
        'A pure function does one thing well. Give calculate_total the cart and the tax rate, and it returns a predictable total — no hidden state, no surprises.',
      slides: [
        {
          kicker: 'Pure functions',
          title: 'One input. One predictable output.',
          points: [
            'The same cart always produces the same total.',
            'Defaults like tax_rate=0.14 document intent at the call site.',
            'Returning a value keeps the function easy to test.',
          ],
          aside: 'calculate_total(cart) → 43.07',
        },
        {
          kicker: 'Scope',
          title: 'Keep data at the edge.',
          points: [
            'Pass data in as arguments instead of reaching for globals.',
            'Keep temporary values local to the function.',
            'Mutating shared state makes bugs travel.',
          ],
          aside: 'Local first. Global never.',
        },
        {
          kicker: 'Refactor',
          title: 'Small functions, obvious names.',
          points: [
            'Name functions after the result, not the steps.',
            'Extract validation from calculation.',
            'If a docstring needs three lines, split the function.',
          ],
          aside: 'A name is a promise.',
        },
      ],
    },
  },
  {
    id: 'flutter',
    title: 'Flutter Interfaces',
    tagline: 'Production-grade mobile UI',
    mark: 'FL',
    accent: 'bg-sky-500/15 text-sky-300 ring-sky-500/25',
    sections: [
      {
        id: 'fl-s1',
        title: 'Dart foundations',
        lessons: [
          { id: 'fl-01', title: 'Dart syntax & null safety', duration: '10 min', completed: true },
          { id: 'fl-02', title: 'Collections & pattern matching', duration: '13 min', completed: true },
          { id: 'fl-03', title: 'Async, futures & streams', duration: '16 min', completed: true },
        ],
      },
      {
        id: 'fl-s2',
        title: 'Flutter UI · Module 03',
        lessons: [
          { id: 'fl-04', title: 'First widgets & hot reload', duration: '12 min', completed: true },
          { id: 'fl-05', title: 'Widgets, Composition & Layout', duration: '22 min', completed: false },
          { id: 'fl-06', title: 'State, rebuilds & controllers', duration: '20 min', completed: false },
          { id: 'fl-07', title: 'Navigation & routes', duration: '18 min', completed: false },
        ],
      },
      {
        id: 'fl-s3',
        title: 'Ship a polished app',
        lessons: [
          { id: 'fl-08', title: 'Animation & implicit motion', duration: '21 min', completed: false },
          { id: 'fl-09', title: 'Theming & design systems', duration: '19 min', completed: false },
          { id: 'fl-10', title: 'Build, test & release', duration: '25 min', completed: false },
        ],
      },
    ],
    lesson: {
      id: 'fl-05',
      module: 'Flutter UI · Module 03',
      title: 'Widgets, Composition & Layout',
      duration: '22 min',
      filename: 'lesson_06_widgets.dart',
      language: 'Dart',
      code: `class LessonCard extends StatelessWidget {
  const LessonCard({super.key, required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF1E2229),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(title),
    );
  }
}`,
      narration:
        'In Flutter every pixel is a widget. LessonCard composes padding, decoration and text into one reusable unit — small pieces that snap together into a polished screen.',
      slides: [
        {
          kicker: 'Composition',
          title: 'Every pixel is a widget.',
          points: [
            'Small widgets compose into complete screens.',
            'Layout is a tree of constraints and sizes.',
            'Reusable pieces keep screens consistent.',
          ],
          aside: 'UI = f(state)',
        },
        {
          kicker: 'Layout',
          title: 'Constraints flow down. Sizes flow up.',
          points: [
            'Parents pass tight or loose constraints to children.',
            'Children choose their size within those limits.',
            'Padding and alignment are layout, not decoration.',
          ],
          aside: 'Constraints → Size → Position',
        },
        {
          kicker: 'Reuse',
          title: 'Build a widget vocabulary.',
          points: [
            'One lesson card, many lesson data objects.',
            'Keep styling inside the component.',
            'Compose new screens from proven parts.',
          ],
          aside: 'Compose small. Reuse often.',
        },
      ],
    },
  },
  {
    id: 'algorithms',
    title: 'Algorithms & Structures',
    tagline: 'Think in complexity',
    mark: 'AL',
    accent: 'bg-violet-500/15 text-violet-300 ring-violet-500/25',
    sections: [
      {
        id: 'al-s1',
        title: 'Foundations',
        lessons: [
          { id: 'al-01', title: 'Big-O without the math anxiety', duration: '11 min', completed: true },
          { id: 'al-02', title: 'Arrays, lists & hash maps', duration: '15 min', completed: true },
          { id: 'al-03', title: 'Recursion with a base case', duration: '14 min', completed: true },
        ],
      },
      {
        id: 'al-s2',
        title: 'Search & Sort · Module 04',
        lessons: [
          { id: 'al-04', title: 'Linear search & sentinels', duration: '9 min', completed: true },
          { id: 'al-05', title: 'Merge sort, step by step', duration: '17 min', completed: true },
          { id: 'al-06', title: 'Quicksort & partitioning', duration: '16 min', completed: true },
          { id: 'al-07', title: 'Binary Search in O(log n)', duration: '15 min', completed: false },
        ],
      },
      {
        id: 'al-s3',
        title: 'Advanced patterns',
        lessons: [
          { id: 'al-08', title: 'Two pointers & sliding windows', duration: '20 min', completed: false },
          { id: 'al-09', title: 'Graphs: BFS and DFS', duration: '23 min', completed: false },
          { id: 'al-10', title: 'Dynamic programming, first pass', duration: '26 min', completed: false },
        ],
      },
    ],
    lesson: {
      id: 'al-07',
      module: 'Search & Sort · Module 04',
      title: 'Binary Search in O(log n)',
      duration: '15 min',
      filename: 'lesson_08_binary_search.py',
      language: 'Python',
      code: `def binary_search(items, target):
    low, high = 0, len(items) - 1

    while low <= high:
        mid = (low + high) // 2
        if items[mid] == target:
            return mid
        if items[mid] < target:
            low = mid + 1
        else:
            high = mid - 1

    return -1`,
      narration:
        'Binary search halves the search space on every pass. Ten steps cover a thousand items, twenty cover a million — this is what logarithmic growth feels like in practice.',
      slides: [
        {
          kicker: 'Divide & conquer',
          title: 'Halve the search space.',
          points: [
            'Compare the target with the middle element.',
            'Discard the half that cannot contain it.',
            'Ten steps cover one thousand items.',
          ],
          aside: 'O(log n) — one halving per step',
        },
        {
          kicker: 'Invariant',
          title: 'Keep the answer inside [low, high].',
          points: [
            'low and high bound the live search window.',
            'Move only the boundary that cannot hold the target.',
            'Stop when the window collapses.',
          ],
          aside: 'low ≤ target index ≤ high',
        },
        {
          kicker: 'Practice',
          title: 'Recognize when the data is sorted.',
          points: [
            'Binary search needs ordered input.',
            'Sorting first costs O(n log n).',
            'Reach for it in lookup-heavy workloads.',
          ],
          aside: 'Sorted data unlocks log time.',
        },
      ],
    },
  },
]

const EXTENSIONS = { Python: 'py', Dart: 'dart' }

function slugify(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40)
}

function buildPracticeCode(language, title, sectionTitle) {
  if (language === 'Dart') {
    return `// ${title}
// ${sectionTitle}

void main() {
  const lesson = '${title}';
  const steps = ['read', 'experiment', 'reflect'];

  for (final step in steps) {
    print('$step: $lesson');
  }
}`
  }

  return `# ${title}
# ${sectionTitle}

def explore():
    lesson = "${title}"
    steps = ["read", "experiment", "reflect"]
    for step in steps:
        print(f"{step}: {lesson}")


if __name__ == "__main__":
    explore()`
}

function buildGeneratedSlides(sectionTitle, lesson) {
  return [
    {
      kicker: sectionTitle,
      title: lesson.title,
      points: [
        `Where ${lesson.title} fits inside ${sectionTitle}.`,
        'The one idea worth remembering.',
        'A guided exercise you can run right away.',
      ],
      aside: 'Concept → Code → Practice',
    },
    {
      kicker: 'Walkthrough',
      title: 'Read the code before you run it.',
      points: [
        'Name the inputs, outputs and side effects.',
        `Trace one example from ${sectionTitle}.`,
        'Change one value and predict the result.',
      ],
      aside: 'Predict → Run → Compare',
    },
    {
      kicker: 'Practice',
      title: 'Your turn at the keyboard.',
      points: [
        'Re-type the example instead of copying it.',
        'Break it on purpose, then repair it.',
        'Explain the fix out loud to lock it in.',
      ],
      aside: 'One small rep beats ten tabs.',
    },
  ]
}

export function flattenLessons(course) {
  return course.sections.flatMap((section, sectionIndex) =>
    section.lessons.map((lesson) => ({
      ...lesson,
      sectionTitle: section.title,
      sectionIndex,
    })),
  )
}

export function resolveLesson(course, lessonId) {
  const allLessons = flattenLessons(course)
  const fallbackId = course.lesson.id
  const entry =
    allLessons.find((lesson) => lesson.id === lessonId) ??
    allLessons.find((lesson) => lesson.id === fallbackId) ??
    allLessons[0]
  const position = allLessons.findIndex((lesson) => lesson.id === entry.id) + 1

  const meta = {
    id: entry.id,
    title: entry.title,
    duration: entry.duration,
    completed: entry.completed,
    module: entry.sectionTitle,
    index: position,
    total: allLessons.length,
  }

  if (entry.id === fallbackId) {
    return { ...course.lesson, ...meta }
  }

  const language = course.lesson.language
  const extension = EXTENSIONS[language] ?? 'txt'

  return {
    ...meta,
    filename: `lesson_${String(position).padStart(2, '0')}_${slugify(entry.title)}.${extension}`,
    language,
    code: buildPracticeCode(language, entry.title, entry.sectionTitle),
    narration: `We are opening ${entry.title}. In ${entry.sectionTitle}, this step turns the idea into something you can run. Follow along in the playground, then raise your hand if anything feels fuzzy.`,
    slides: buildGeneratedSlides(entry.sectionTitle, entry),
  }
}
