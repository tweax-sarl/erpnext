# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import unittest

import frappe
from frappe.utils.data import add_days, formatdate, today

from erpnext.maintenance.doctype.maintenance_schedule.maintenance_schedule import (
	get_serial_nos_from_schedule,
	make_maintenance_visit,
)
from erpnext.stock.doctype.item.test_item import create_item
from erpnext.stock.doctype.stock_entry.test_stock_entry import make_serialized_item

# test_records = frappe.get_test_records('Maintenance Schedule')

class TestMaintenanceSchedule(unittest.TestCase):
	def test_events_should_be_created_and_deleted(self):
		ms = make_maintenance_schedule()
		ms.generate_schedule()
		ms.submit()

		all_events = get_events(ms)
		self.assertTrue(len(all_events) > 0)

		ms.cancel()
		events_after_cancel = get_events(ms)
		self.assertTrue(len(events_after_cancel) == 0)

	def test_make_schedule(self):
		ms = make_maintenance_schedule()
		ms.save()
		i = ms.items[0]
		expected_dates = []
		expected_end_date = add_days(i.start_date, i.no_of_visits * 7)
		self.assertEqual(i.end_date, expected_end_date)

		i.no_of_visits = 2
		ms.save()
		expected_end_date = add_days(i.start_date, i.no_of_visits * 7)
		self.assertEqual(i.end_date, expected_end_date)

		items = ms.get_pending_data(data_type = "items")
		items = items.split('\n')
		items.pop(0)
		expected_items = ['_Test Item']
		self.assertTrue(items, expected_items)

		# "dates" contains all generated schedule dates
		dates = ms.get_pending_data(data_type = "date", item_name = i.item_name)
		dates = dates.split('\n')
		dates.pop(0)
		expected_dates.append(formatdate(add_days(i.start_date, 7), "dd-MM-yyyy"))
		expected_dates.append(formatdate(add_days(i.start_date, 14), "dd-MM-yyyy"))

		# test for generated schedule dates
		self.assertEqual(dates, expected_dates)

		ms.submit()
		s_id = ms.get_pending_data(data_type = "id", item_name = i.item_name, s_date = expected_dates[1])

		# Check if item is mapped in visit.
		test_map_visit = make_maintenance_visit(source_name = ms.name, item_name = "_Test Item", s_id = s_id)
		self.assertEqual(len(test_map_visit.purposes), 1)
		self.assertEqual(test_map_visit.purposes[0].item_name, "_Test Item")

		visit = frappe.new_doc('Maintenance Visit')
		visit = test_map_visit
		visit.maintenance_schedule = ms.name
		visit.maintenance_schedule_detail = s_id
		visit.completion_status = "Partially Completed"
		visit.set('purposes', [{
			'item_code': i.item_code,
			'description': "test",
			'work_done': "test",
			'service_person': "Sales Team",
		}])
		visit.save()
		visit.submit()
		ms = frappe.get_doc('Maintenance Schedule', ms.name)

		#checks if visit status is back updated in schedule
		self.assertTrue(ms.schedules[1].completion_status, "Partially Completed")

	def test_serial_no_filters(self):
		# Without serial no. set in schedule -> returns None
		item_code = "_Test Serial Item"
		make_serial_item_with_serial(item_code)
		ms = make_maintenance_schedule(item_code=item_code)
		ms.submit()

		s_item = ms.schedules[0]
		mv = make_maintenance_visit(source_name=ms.name, item_name=item_code, s_id=s_item.name)
		mvi = mv.purposes[0]
		serial_nos = get_serial_nos_from_schedule(mvi.item_name, ms.name)
		self.assertEqual(serial_nos, None)

		# With serial no. set in schedule -> returns serial nos.
		make_serial_item_with_serial(item_code)
		ms = make_maintenance_schedule(item_code=item_code, serial_no="TEST001, TEST002")
		ms.submit()

		s_item = ms.schedules[0]
		mv = make_maintenance_visit(source_name=ms.name, item_name=item_code, s_id=s_item.name)
		mvi = mv.purposes[0]
		serial_nos = get_serial_nos_from_schedule(mvi.item_name, ms.name)
		self.assertEqual(serial_nos, ["TEST001", "TEST002"])

		frappe.db.rollback()

def make_serial_item_with_serial(item_code):
	serial_item_doc = create_item(item_code, is_stock_item=1)
	if not serial_item_doc.has_serial_no or not serial_item_doc.serial_no_series:
		serial_item_doc.has_serial_no = 1
		serial_item_doc.serial_no_series = "TEST.###"
		serial_item_doc.save(ignore_permissions=True)
	active_serials = frappe.db.get_all('Serial No', {"status": "Active", "item_code": item_code})
	if len(active_serials) < 2:
		make_serialized_item(item_code=item_code)

def get_events(ms):
	return frappe.get_all("Event Participants", filters={
			"reference_doctype": ms.doctype,
			"reference_docname": ms.name,
			"parenttype": "Event"
		})

def make_maintenance_schedule(**args):
	ms = frappe.new_doc("Maintenance Schedule")
	ms.company = "_Test Company"
	ms.customer = "_Test Customer"
	ms.transaction_date = today()

	ms.append("items", {
		"item_code": args.get("item_code") or "_Test Item",
		"start_date": today(),
		"periodicity": "Weekly",
		"no_of_visits": 4,
		"serial_no": args.get("serial_no"),
		"sales_person": "Sales Team",
	})
	ms.insert(ignore_permissions=True)

	return ms
