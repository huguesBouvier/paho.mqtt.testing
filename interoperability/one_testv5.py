"""
*******************************************************************
  Copyright (c) 2013, 2018 IBM Corp.

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

import mqtt.clients.V5 as mqtt_client, time, logging, socket, sys, getopt, traceback
import mqtt.formats.MQTTV5 as MQTTV5

class Callbacks(mqtt_client.Callback):

  def __init__(self):
    self.messages = []
    self.messagedicts = []
    self.publisheds = []
    self.subscribeds = []
    self.unsubscribeds = []
    self.disconnects = []

  def __str__(self):
     return str(self.messages) + str(self.messagedicts) + str(self.publisheds) + \
        str(self.subscribeds) + str(self.unsubscribeds) + str(self.disconnects)

  def clear(self):
    self.__init__()

  def disconnected(self, reasoncode, properties):
    logging.info("disconnected %s %s", str(reasoncode), str(properties))
    self.disconnects.append({"reasonCode" : reasoncode, "properties" : properties})

  def connectionLost(self, cause):
    logging.info("connectionLost %s" % str(cause))

  def publishArrived(self, topicName, payload, qos, retained, msgid, properties=None):
    logging.info("publishArrived %s %s %d %s %d %s", topicName, payload, qos, retained, msgid, str(properties))
    self.messages.append((topicName, payload, qos, retained, msgid, properties))
    self.messagedicts.append({"topicname" : topicName, "payload" : payload,
        "qos" : qos, "retained" : retained, "msgid" : msgid, "properties" : properties})
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

def cleanRetained():
  callback = Callbacks()
  curclient = mqtt_client.Client("clean retained".encode("utf-8"))
  curclient.registerCallback(callback)
  time.sleep(1)
  curclient.connect(host=host, port=port, cleanstart=True)
  time.sleep(1)
  curclient.subscribe(["#"], [MQTTV5.SubscribeOptions(0)])
  time.sleep(2) # wait for all retained messages to arrive
  for message in callback.messages:
    logging.info("deleting retained message for topic", message[0])
    curclient.publish(message[0], b"", 0, retained=True)
  curclient.disconnect()
  time.sleep(.1)

def cleanup():
  # clean all client state
  print("clean up starting")
  clientids = ("myclientid", "myclientid2")

  for clientid in clientids:
    curclient = mqtt_client.Client(clientid.encode("utf-8"))
    curclient.connect(host=host, port=port, cleanstart=True)
    time.sleep(.1)
    curclient.disconnect()
    time.sleep(.1)

  # clean retained messages
  cleanRetained()
  print("clean up finished")

def usage():
  logging.info(
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
      setData()
      global callback, callback2, aclient, bclient
      #cleanup()

      callback = Callbacks()
      callback2 = Callbacks()

      #aclient = mqtt_client.Client(b"\xEF\xBB\xBF" + "myclientid".encode("utf-8"))
      aclient = mqtt_client.Client("myclientid".encode("utf-8"))
      aclient.registerCallback(callback)

      bclient = mqtt_client.Client("myclientid2".encode("utf-8"))
      bclient.registerCallback(callback2)

    def waitfor(self, queue, depth, limit):
      total = 0
      while len(queue) < depth and total < limit:
        interval = .5
        total += interval
        time.sleep(interval)


    def test_request_response(self):
      callback.clear()
      callback2.clear()

      aclient.connect(host=host, port=port, cleanstart=True)
      bclient.connect(host=host, port=port, cleanstart=True)
      aclient.subscribe([topics[0]], [MQTTV5.SubscribeOptions(2, noLocal=True)])
      self.waitfor(callback.subscribeds, 1, 3)

      bclient.subscribe([topics[0]], [MQTTV5.SubscribeOptions(2, noLocal=True)])
      self.waitfor(callback.subscribeds, 1, 3)

      publish_properties = MQTTV5.Properties(MQTTV5.PacketTypes.PUBLISH)
      publish_properties.ResponseTopic = topics[0]
      publish_properties.CorrelationData = b"334"
      # client a is the requester
      aclient.publish(topics[0], b"request", 1, properties=publish_properties)

      # client b is the responder
      self.waitfor(callback2.messages, 1, 3)
      self.assertEqual(len(callback2.messages), 1, callback2.messages)

      self.assertEqual(len(callback2.messages), 1, callback2.messages)
      self.assertEqual(callback2.messages[0][5].ResponseTopic, topics[0],
                       callback2.messages[0][5])
      self.assertEqual(callback2.messages[0][5].CorrelationData, b"334",
                       callback2.messages[0][5])

      bclient.publish(callback2.messages[0][5].ResponseTopic, b"response", 1,
                      properties=callback2.messages[0][5])

      # client a gets the response
      self.waitfor(callback.messages, 1, 3)
      self.assertEqual(len(callback.messages), 1, callback.messages)

      aclient.disconnect()
      bclient.disconnect()

      callback.clear()
      callback2.clear()

def setData():
  global topics, wildtopics, nosubscribe_topics, host, port
  topics =  ("TopicA", "TopicA/B", "Topic/C", "TopicA/C", "/TopicA")
  wildtopics = ("TopicA/+", "+/C", "#", "/#", "/+", "+/+", "TopicA/#")
  nosubscribe_topics = ("test/nosubscribe",)


if __name__ == "__main__":
  try:
    opts, args = getopt.gnu_getopt(sys.argv[1:], "h:p:vzdsn:",
      ["help", "hostname=", "port=", "iterations="])
  except getopt.GetoptError as err:
    logging.info(err) # will print something like "option -a not recognized"
    usage()
    sys.exit(2)

  iterations = 1

  global topics, wildtopics, nosubscribe_topics, host, topic_prefix
  topic_prefix = "client_test5/"
  topics = [topic_prefix+topic for topic in ["TopicA", "TopicA/B", "Topic/C", "TopicA/C", "/TopicA"]]
  wildtopics = [topic_prefix+topic for topic in ["TopicA/+", "+/C", "#", "/#", "/+", "+/+", "TopicA/#"]]
  print(wildtopics)
  nosubscribe_topics = ("test/nosubscribe",)

  host = "frontend1-0.frontend1.default.svc.cluster.local"
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
      sys.argv.remove("-p") if "-p" in sys.argv else sys.argv.remove("--port")
      sys.argv.remove(a)
    elif o in ("--iterations"):
      iterations = int(a)

  root = logging.getLogger()
  root.setLevel(logging.ERROR)

  logging.info("hostname %s port %d", host, port)
  print("argv", sys.argv)
  for i in range(iterations):
    unittest.main()
