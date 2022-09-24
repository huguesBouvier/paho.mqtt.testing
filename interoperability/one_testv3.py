"""
*******************************************************************
  Copyright (c) 2013, 2017 IBM Corp.

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

import unittest

import mqtt.clients.V311 as mqtt_client, time, logging, socket, sys, getopt, traceback

class Callbacks(mqtt_client.Callback):

  def __init__(self):
    self.messages = []
    self.publisheds = []
    self.subscribeds = []
    self.unsubscribeds = []

  def clear(self):
    self.__init__()

  def connectionLost(self, cause):
    logging.info("connectionLost %s", str(cause))

  def publishArrived(self, topicName, payload, qos, retained, msgid):
    logging.info("publishArrived %s %s %d %d %d", topicName, payload, qos, retained, msgid)
    self.messages.append((topicName, payload, qos, retained, msgid))
    return True

  def published(self, msgid):
    logging.info("published %d", msgid)
    self.publisheds.append(msgid)

  def subscribed(self, msgid, data):
    logging.info("subscribed %d", msgid)
    self.subscribeds.append((msgid, data))

  def unsubscribed(self, msgid):
    logging.info("unsubscribed %d", msgid)
    self.unsubscribeds.append(msgid)

def cleanup():
  # clean all client state
  print("clean up starting")
  clientids = ("myclientid", "myclientid2")

  for clientid in clientids:
    curclient = mqtt_client.Client(clientid.encode("utf-8"))
    curclient.connect(host=host, port=port, cleansession=True)
    time.sleep(.1)
    curclient.disconnect()
    time.sleep(.1)

  # clean retained messages
  callback = Callbacks()
  curclient = mqtt_client.Client("clean retained".encode("utf-8"))
  curclient.registerCallback(callback)
  curclient.connect(host=host, port=port, cleansession=True)
  curclient.subscribe(["#"], [0])
  time.sleep(2) # wait for all retained messages to arrive
  for message in callback.messages:
    if message[3]: # retained flag
      print("deleting retained message for topic", message[0])
      curclient.publish(message[0], b"", 0, retained=True)
  curclient.disconnect()
  time.sleep(.1)
  print("clean up finished")

def usage():
  print(
"""
 -h: --hostname= hostname or ip address of server to run tests against
 -p: --port= port number of server to run tests against
 -z: --zero_length_clientid run zero length clientid test
 -d: --dollar_topics run $ topics test
 -s: --subscribe_failure run subscribe failure test
 -n: --nosubscribe_topic_filter= topic filter name for which subscriptions aren't allowed

""")

class Test(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
      global callback, callback2, aclient, bclient
      cleanup()

      callback = Callbacks()
      callback2 = Callbacks()

      #aclient = mqtt_client.Client(b"\xEF\xBB\xBF" + "myclientid".encode("utf-8"))
      aclient = mqtt_client.Client("myclientid".encode("utf-8"))
      aclient.registerCallback(callback)

      bclient = mqtt_client.Client("myclientid2".encode("utf-8"))
      bclient.registerCallback(callback2)

    def test_redelivery_on_reconnect(self):
      # redelivery on reconnect. When a QoS 1 or 2 exchange has not been completed, the server should retry the
      # appropriate MQTT packets
      print("Redelivery on reconnect test starting")
      succeeded = True
      try:
        callback.clear()
        callback2.clear()
        bclient.connect(host=host, port=port, cleansession=False)
        time.sleep(1)
        bclient.subscribe([topics[1]], [2])
        time.sleep(1)
        bclient.pause() # stops responding to incoming publishes
        bclient.publish(topics[1], b"", 1, retained=False)
        time.sleep(1)
        bclient.disconnect()
        assert len(callback2.messages) == 0, "length should be 0: %s" % callback2.messages
        time.sleep(1)
        bclient.resume()
        bclient.connect(host=host, port=port, cleansession=False)
        time.sleep(3)
        assert len(callback2.messages) == 1, "length should be 1: %s" % callback2.messages
        bclient.disconnect()
      except:
        traceback.print_exc()
        succeeded = False
      print("Redelivery on reconnect test", "succeeded" if succeeded else "failed")
      self.assertEqual(succeeded, True)
      return succeeded

if __name__ == "__main__":
  try:
    opts, args = getopt.gnu_getopt(sys.argv[1:], "h:p:zdsn:",
      ["help", "hostname=", "port=", "iterations="])
  except getopt.GetoptError as err:
    print(err) # will print something like "option -a not recognized"
    usage()
    sys.exit(2)

  iterations = 1

  global topics, wildtopics, nosubscribe_topics
  topics =  ("TopicA", "TopicA/B", "Topic/C", "TopicA/C", "/TopicA")
  wildtopics = ("TopicA/+", "+/C", "#", "/#", "/+", "+/+", "TopicA/#")
  nosubscribe_topics = ("test/nosubscribe",)

  #host = "frontend1-0.frontend1.default.svc.cluster.local"
  host = "192.168.49.2"
  port = 1883

  for o, a in opts:
    if o in ("--help"):
      usage()
      sys.exit()
    elif o in ("-n", "--nosubscribe_topic_filter"):
      nosubscribe_topic_filter = a
    elif o in ("-h", "--hostname"):
      host = a
    elif o in ("-p", "--port"):
      port = int(a)
    elif o in ("--iterations"):
      iterations = int(a)
    else:
      assert False, "unhandled option"

  root = logging.getLogger()
  root.setLevel(logging.ERROR)

  print("hostname", host, "port", port)

  for i in range(iterations):
    unittest.main()
