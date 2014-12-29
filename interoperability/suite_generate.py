"""
*******************************************************************
  Copyright (c) 2013, 2014 IBM Corp.
 
  All rights reserved. This program and the accompanying materials
  are made available under the terms of the Eclipse Public License v1.0
  and Eclipse Distribution License v1.0 which accompany this distribution. 
 
  The Eclipse Public License is available at 
     http://www.eclipse.org/legal/epl-v10.html
  and the Eclipse Distribution License is available at 
    http://www.eclipse.org/org/documents/edl-v10.php.
 
  Contributors:
     Ian Craggs - initial implementation and/or documentation
*******************************************************************
"""

"""

1. Start the model broker.  Clean state.

2. Run the spec, one step at a time until conformance statement hit.

3. Reduce sequence to shortest.

4. Store.


Repeat until all conformance statements hit.

Do store tests that reach a conformance statement in a different way.

"""

import os, shutil, threading, time, logging, logging.handlers, queue, sys

import mqtt, MQTTV311_spec

class Brokers(threading.Thread):

  def __init__(self):
    threading.Thread.__init__(self)

  def run(self):
    mqtt.broker.run()
    while not mqtt.broker.server:
      time.sleep(.1)
    time.sleep(1)

  def stop(self):
    mqtt.broker.stop()
    while mqtt.broker.server:
      time.sleep(.1) 
    time.sleep(1)

  def reinitialize(self):
    mqtt.broker.reinitialize()

qlog = queue.Queue()
qh = logging.handlers.QueueHandler(qlog)
formatter = logging.Formatter(fmt='%(levelname)s %(asctime)s %(name)s %(message)s',  datefmt='%Y%m%d %H%M%S')
qh.setFormatter(formatter)
qh.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(formatter)
ch.setLevel(logging.ERROR)
broker_logger = logging.getLogger('MQTT broker')
broker_logger.addHandler(qh)
broker_logger.propagate = False
#broker_logger.addHandler(ch)

logger = logging.getLogger('suite_generate')
logger.setLevel(logging.INFO)
#formatter = logging.Formatter(fmt='%(levelname)s %(asctime)s %(name)s %(message)s',  datefmt='%Y%m%d %H%M%S')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
ch.setLevel(logging.INFO)
logger.addHandler(ch)
logger.propagate = False


def create():
	global logger, qlog
	conformances = set([])
	restart = False
	while not restart:
		logger.debug("stepping")
		restart = MQTTV311_spec.mbt.step()
		logger.debug("stepped")
		data = qlog.get().getMessage()
		logger.debug("data %s", data)
		while data and data.find("Waiting for request") == -1 and data.find("Finishing communications") == -1:
			if data.find("[MQTT") != -1:
				logger.debug("Conformance statement %s", data)
				conformances.add(data + "\n" if data[-1] != "\n" else data)
			data = qlog.get().getMessage()
			logger.debug("data %s", data)
		#if input("--->") == "q":
		#		return
	return conformances


if __name__ == "__main__":
	#try:
	os.system("rm -rf tests")
	#except:
	#	pass
	os.mkdir("tests")
	test_no = 0
	logger.info("Generation starting")

	broker = Brokers() 
	broker.start()
	last_measures = None
	stored_tests = 0
	while stored_tests < 10 and test_no < 30:
		test_no += 1
		conformance_statements = create()
		cur_measures = mqtt.broker.coverage.getmeasures()[:2]

		# now tests/test.%d has the test
		filename = "tests/test.log.%d" % (test_no,)
		if cur_measures == last_measures:
			os.system("rm "+filename)
		else:
			stored_tests += 1
			logger.info("Test %d created", stored_tests)
			infile = open(filename)
			lines = infile.readlines()
			infile.close()
			outfile = open(filename, "w")
			outfile.writelines(list(conformance_statements) + lines)
			outfile.close()
			print(cur_measures)
			last_measures = cur_measures
	
			#shorten()
			#store()
		broker.reinitialize()

	broker.stop()
	print(mqtt.broker.coverage.getmeasures())
	logger.info("Generation complete")

	# Without the following, background threads cause the process not to stop
	for t in threading.enumerate():
		print(t.name)
		try:
			t._stop()
		except:
			pass

