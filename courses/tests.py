import sys
import os
import datetime

from django.utils import unittest
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.conf import settings
from django.core.files import File

from courses.models import Course, Semester, Assignment, AssignmentSubmission

import libs.test_utils as test_utils

one_week = datetime.timedelta(7)
one_day = datetime.timedelta(1)

class SemesterTest(test_utils.AuthenticatedTest):
    def test_create(self):
        semester = Semester(name='Spring', year = '2012', start = datetime.date(2012, 1, 1), end = datetime.date(2012, 5, 15))
        semester.save()
        self.assertEquals(semester.name, 'Spring')
        self.assertEquals(semester.year, '2012')
        self.assertEquals(semester.start, datetime.date(2012, 1, 1))
        self.assertEquals(semester.end, datetime.date(2012, 5, 15))
        semester.delete()

        # Try invalid start and end date
        semester = Semester(name='Spring', year = '2012', start = datetime.date(2012, 5, 15), end = datetime.date(2012, 1, 1))
        self.assertRaises(ValueError, semester.save, ())
        
    def test_listing(self):
        semester = Semester(name='Spring', year = '2012', start = datetime.date(2012, 1, 1), end = datetime.date(2012, 5, 15))
        semester.save()

        course = Course(title='Test Course', number = '101', section = '001', description = 'Test description of a course', semester = semester)
        course.save()
        course = Course(title='Test Course2', number = '101', section = '002', description = 'Test description of a course', semester = semester)
        course.save()
        course = Course(title='Test Course3', number = '102', section = '001', description = 'Test description of a course', semester = semester)
        course.save()

        response = self.c.get(reverse('courses:by_semester', args = [semester.id]))
        courses = Course.objects.filter(semester = semester)
        self.assertEquals([course.id for course in response.context['courses']], [course.id for course in courses])

    def test_active(self):
        semester = Semester(name='Spring', year = '2012', start = datetime.date.today() - one_day, end = datetime.date.today() + one_day)
        semester.save()

        self.assertEquals(semester.active(), True)

        semester.start = datetime.date.today() + one_day
        semester.end = datetime.date.today() + one_week
        semester.save()

        self.assertEquals(semester.active(), False)
        


class CoursesTest(test_utils.AuthenticatedTest):
    def setUp(self):
        super(CoursesTest, self).setUp()
        self.semester = Semester(name='Spring', year = '2012', start = datetime.date(2012, 1, 1), end = datetime.date(2012, 5, 1))
        self.semester.save()
        self.course = Course(title='Test Course', number = '101', section = '001', description = 'Test description of a course', semester = self.semester)
        self.course.save()
        

    def tearDown(self):
        self.course.delete()
        self.semester.delete()

    def test_create(self):
        self.assertEquals(self.course.title, 'Test Course')
        self.assertEquals(self.course.number, '101')
        self.assertEquals(self.course.section, '001')
        self.assertEquals(self.course.description, 'Test description of a course')

    def test_view(self):
        response = self.c.get(reverse('courses:overview', args = [self.course.id]))

        self.assertEquals(response.context['course'].title, 'Test Course')
        self.assertEquals(response.context['course'].number, '101')
        self.assertEquals(response.context['course'].section, '001')
        self.assertEquals(response.context['course'].description, 'Test description of a course')

    def test_access(self):
        self.course.private = True
        self.course.save()

        response = self.c.get(reverse('courses:overview', args = [self.course.id]))
        self.assertEquals(response.status_code, 403)

        # Test membership
        self.course.members.add(self.user)
        response = self.c.get(reverse('courses:overview', args = [self.course.id]))
        self.assertEquals(response.status_code, 200)
        self.course.members.remove(self.user)

        # Test Faculty
        self.course.faculty.add(self.user)
        response = self.c.get(reverse('courses:overview', args = [self.course.id]))
        self.assertEquals(response.status_code, 200)
        self.course.faculty.remove(self.user)

        self.course.private = False
        self.course.save()

class AssignmentTest(test_utils.AuthenticatedTest):
    def setUp(self):
        super(AssignmentTest, self).setUp()
        self.semester = Semester(name='Spring', year = '2012', start = datetime.date(2012, 1, 1), end = datetime.date(2012, 5, 1))
        self.semester.save()
        self.course = Course(title='Test Course', number = '101', section = '001', description = 'Test description of a course', semester = self.semester)
        self.course.save()

    def tearDown(self):
        super(AssignmentTest, self).tearDown()
        self.course.delete()
        self.semester.delete()

    def test_create(self):
        # Add client user as faculty member
        self.course.faculty.add(self.user)
        self.course.save()

        # Test we get the form
        response = self.c.get(reverse('courses:new_assignment', kwargs = {'pk':self.course.id}))
        self.assertEquals(response.status_code, 200)

        response = self.c.post(reverse('courses:new_assignment', kwargs = {'pk':self.course.id}), {'course':self.course.id,
                                                                                            'title':'Test Assignment',
                                                                                            'description':'Test of the description <b>HERE</b>',
                                                                                            'due_date': (datetime.date.today() + one_week).isoformat()})

        self.assertEquals(response.status_code, 302)

        # Remove user
        self.course.faculty.remove(self.user)


    def test_list(self):
        assignment = Assignment(course = self.course, title = "Test Assignment", description = 'Test of the description <b>HERE</b>', due_date = (datetime.date.today() + one_week).isoformat())
        assignment.save()

        # Add client user as faculty member
        self.course.faculty.add(self.user)
        self.course.save()
        
        response = self.c.get(reverse('courses:assignments', kwargs = {'pk':self.course.id}))

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.context['assignments'][0], assignment)

        # Remove user
        self.course.faculty.remove(self.user)

    def test_submit(self):
        # Add client user as faculty member
        self.course.faculty.add(self.user)
        self.course.save()
        response = self.c.post(reverse('courses:new_assignment', kwargs = {'pk':self.course.id}), {'course':self.course.id,
                                                                                            'title':'Test Assignment',
                                                                                            'description':'Test of the description <b>HERE</b>',
                                                                                            'due_date': (datetime.date.today() + one_week).isoformat()})

        # Remove user
        self.course.faculty.remove(self.user)

        self.course.members.add(self.user)

        assignment = Assignment.objects.get(course = self.course, title = 'Test Assignment')

        # Test submitting solution
        response = self.c.post(reverse('courses:submit_assignment', kwargs = {'pk':assignment.id}), {'link':'http://www.example.com',
                                                                                                     'notes':'Test notes.',})
        self.assertEquals(response.status_code, 302)

        self.course.members.remove(self.user)

    def test_delete_submission(self):
        # We overrode the delete, so we should be testing it
        self.course.members.add(self.user)

        assignment = Assignment(course = self.course, title = "Test Assignment", description = 'Test of the description <b>HERE</b>', due_date = (datetime.date.today() + one_week).isoformat())
        assignment.save()

        submission = AssignmentSubmission(assignment = assignment, link = "http://www.example.com", notes = "Test notes.")
        submission.save()
        submission.users.add(self.user)
        submission.save()

        s_id = submission.id

        response = self.c.post(reverse('courses:delete_submission'), {'id': submission.id})

        self.assertEquals(response.content, reverse('courses:assignment_overview', kwargs = {'pk': assignment.id}))

        self.assertRaises(AssignmentSubmission.DoesNotExist, AssignmentSubmission.objects.get, pk = s_id)
