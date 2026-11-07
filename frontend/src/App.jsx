import { useState } from 'react'
import CurriculumSidebar from './components/CurriculumSidebar'
import FloatingProfessor from './components/FloatingProfessor'
import Header from './components/Header'
import SmartPlayer from './components/SmartPlayer'
import { COURSES, resolveLesson } from './data/courses'

export default function App() {
  const [selectedCourseId, setSelectedCourseId] = useState(COURSES[0].id)
  const [selectedLessonId, setSelectedLessonId] = useState(COURSES[0].lesson.id)
  const [avatarStatus, setAvatarStatus] = useState('idle')

  const course = COURSES.find((item) => item.id === selectedCourseId) ?? COURSES[0]
  const lesson = resolveLesson(course, selectedLessonId)

  const handleSelectCourse = (courseId) => {
    const nextCourse = COURSES.find((item) => item.id === courseId)
    if (!nextCourse) return
    setSelectedCourseId(courseId)
    setSelectedLessonId(nextCourse.lesson.id)
    setAvatarStatus('idle')
  }

  const handleSelectLesson = (lessonId) => {
    setSelectedLessonId(lessonId)
    setAvatarStatus('idle')
  }

  return (
    <div className="min-h-screen">
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-0 bg-grid opacity-40" />

      <div className="relative z-10 flex min-h-screen flex-col">
        <Header />

        <main id="classroom" className="mx-auto w-full max-w-[1920px] flex-1">
          <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px]">
            <section className="min-w-0 px-4 pb-10 pt-4 sm:px-5 sm:pt-5 lg:px-6">
              <SmartPlayer
                key={lesson.id}
                lesson={lesson}
                courseTitle={course.title}
                status={avatarStatus}
              />

              <FloatingProfessor status={avatarStatus} onStatusChange={setAvatarStatus} />
            </section>

            <div className="order-2 mx-4 mb-8 xl:m-0 xl:border-l xl:border-white/[0.06] xl:bg-abyss-850">
              <CurriculumSidebar
                key={course.id}
                courses={COURSES}
                course={course}
                selectedLessonId={lesson.id}
                onSelectCourse={handleSelectCourse}
                onSelectLesson={handleSelectLesson}
                className="xl:sticky xl:top-[73px] xl:h-[calc(100vh-73px)] xl:rounded-none xl:border-0 xl:bg-none xl:bg-transparent xl:shadow-none xl:backdrop-blur-none"
              />
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
