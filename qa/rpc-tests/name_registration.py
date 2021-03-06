#!/usr/bin/env python3
# Copyright (c) 2014-2016 Daniel Kraft
# Distributed under the MIT/X11 software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

# RPC test for basic name registration and access (name_show, name_history).

from test_framework.names import NameTestFramework
from test_framework.util import *

class NameRegistrationTest (NameTestFramework):

  def run_test (self):
    # Perform name_new's.  Check for too long names exception.
    newA = self.nodes[0].name_new ("node-0")
    newAconfl = self.nodes[1].name_new ("node-0")
    newB = self.nodes[1].name_new ("node-1")
    self.nodes[0].name_new ("x" * 255)
    try:
      self.nodes[0].name_new ("x" * 256)
      raise AssertionError ("too long name not recognised by name_new")
    except JSONRPCException as exc:
      assert_equal (exc.error['code'], -8)
    self.generate (0, 5)

    # Check for exception with name_history and without -namehistory.
    try:
      self.nodes[0].name_history ("node-0")
      raise AssertionError ("name_history without -namehistory works")
    except JSONRPCException as exc:
      assert_equal (exc.error['code'], -1)

    # first_update the names.  Check for too long values.
    addrA = self.nodes[0].getnewaddress ()
    txidA = self.firstupdateName (0, "node-0", newA, "value-0", addrA)
    try:
      self.firstupdateName (1, "node-1", newB, "x" * 521)
      raise AssertionError ("too long value not recognised by name_firstupdate")
    except JSONRPCException as exc:
      assert_equal (exc.error['code'], -8)
    self.firstupdateName (1, "node-1", newB, "x" * 520)

    # Check for mempool conflict detection with registration of "node-0".
    self.sync_all ()
    try:
      self.firstupdateName (1, "node-0", newAconfl, "foo")
      raise AssertionError ("name_firstupdate didn't catch conflict")
    except JSONRPCException as exc:
      assert_equal (exc.error['code'], -25)
    
    # Check that the name appears when the name_new is ripe.

    self.generate (0, 7)
    try:
      self.nodes[1].name_show ("node-0")
      raise AssertionError ("name available when it should not yet be")
    except JSONRPCException as exc:
      assert_equal (exc.error['code'], -4)
    try:
      self.nodes[1].name_history ("node-0")
      raise AssertionError ("name available when it should not yet be")
    except JSONRPCException as exc:
      assert_equal (exc.error['code'], -4)
    self.generate (0, 1)

    data = self.checkName (1, "node-0", "value-0", 30, False)
    assert_equal (data['address'], addrA)
    assert_equal (data['txid'], txidA)
    assert_equal (data['height'], 213)

    self.checkNameHistory (1, "node-0", ["value-0"])
    self.checkNameHistory (1, "node-1", ["x" * 520])

    # Check for error with rand mismatch (wrong name)
    newA = self.nodes[0].name_new ("test-name")
    self.generate (0, 10)
    try:
      self.firstupdateName (0, "test-name-wrong", newA, "value")
      raise AssertionError ("wrong rand value not caught by name_firstupdate")
    except JSONRPCException as exc:
      assert_equal (exc.error['code'], -25)

    # Check for mismatch with prev tx from another node for name_firstupdate
    # and name_update.
    try:
      self.firstupdateName (1, "test-name", newA, "value")
      raise AssertionError ("wrong node can firstupdate a name")
    except JSONRPCException as exc:
      assert_equal (exc.error['code'], -4)
    self.firstupdateName (0, "test-name", newA, "test-value")

    # Check for disallowed firstupdate when the name is active.
    newSteal = self.nodes[1].name_new ("node-0")
    newSteal2 = self.nodes[1].name_new ("node-0")
    self.generate (0, 19)
    self.checkName (1, "node-0", "value-0", 1, False)
    try:
      self.firstupdateName (1, "node-0", newSteal, "stolen")
      raise AssertionError ("name stolen before expiry")
    except JSONRPCException as exc:
      assert_equal (exc.error['code'], -25)

    # Check for "stealing" of the name after expiry.
    self.generate (0, 1)
    self.firstupdateName (1, "node-0", newSteal, "stolen")
    self.checkName (1, "node-0", "value-0", 0, True)
    self.generate (0, 1)
    self.checkName (1, "node-0", "stolen", 30, False)
    self.checkNameHistory (1, "node-0", ["value-0", "stolen"])

    # Check for firstupdating an active name, but this time without the check
    # present in the RPC call itself.  This should still be prevented by the
    # mempool logic.  There was a bug that allowed these transactiosn to get
    # into the mempool, so make sure it is no longer there.
    self.firstupdateName (1, "node-0", newSteal2, "unstolen",
                          allowActive = True)
    assert_equal (self.nodes[1].getrawmempool (), [])
    self.checkName (1, "node-0", "stolen", None, False)

    # Check basic updating.
    try:
      self.nodes[0].name_update ("test-name", "x" * 521)
      raise AssertionError ("update to too long value allowed")
    except JSONRPCException as exc:
      assert_equal (exc.error['code'], -8)
    self.nodes[0].name_update ("test-name", "x" * 520)
    self.checkName (0, "test-name", "test-value", None, False)
    self.generate (0, 1)
    self.checkName (1, "test-name", "x" * 520, 30, False)
    self.checkNameHistory (1, "test-name", ["test-value", "x" * 520])

    addrB = self.nodes[1].getnewaddress ()
    self.nodes[0].name_update ("test-name", "sent", addrB)
    self.generate (0, 1)
    data = self.checkName (0, "test-name", "sent", 30, False)
    assert_equal (data['address'], addrB)
    self.nodes[1].name_update ("test-name", "updated")
    self.generate (0, 1)
    data = self.checkName (0, "test-name", "updated", 30, False)
    self.checkNameHistory (1, "test-name",
                           ["test-value", "x" * 520, "sent", "updated"])

    # Invalid updates.
    try:
      self.nodes[1].name_update ("wrong-name", "foo")
      raise AssertionError ("invalid name updated")
    except JSONRPCException as exc:
      assert_equal (exc.error['code'], -25)
    try:
      self.nodes[0].name_update ("test-name", "stolen?")
      raise AssertionError ("wrong node could update sent name")
    except JSONRPCException as exc:
      assert_equal (exc.error['code'], -4)

    # Reject update when another update is pending.
    self.nodes[1].name_update ("test-name", "value")
    try:
      self.nodes[1].name_update ("test-name", "new value")
      raise AssertionError ("name_update didn't catch pending other update")
    except JSONRPCException as exc:
      assert_equal (exc.error['code'], -25)
    self.generate (0, 1)
    data = self.checkName (0, "test-name", "value", 30, False)
    self.checkNameHistory (1, "test-name", ["test-value", "x" * 520, "sent",
                                            "updated", "value"])
    
    # Update failing after expiry.  Re-registration possible.
    self.checkName (1, "node-1", "x" * 520, None, True)
    try:
      self.nodes[1].name_update ("node-1", "updated?")
      raise AssertionError ("expired name updated")
    except JSONRPCException as exc:
      assert_equal (exc.error['code'], -25)

    newSteal = self.nodes[0].name_new ("node-1")
    self.generate (0, 10)
    self.firstupdateName (0, "node-1", newSteal, "reregistered")
    self.generate (0, 10)
    self.checkName (1, "node-1", "reregistered", 23, False)
    self.checkNameHistory (1, "node-1", ["x" * 520, "reregistered"])

    # Test that name updates are even possible with less balance in the wallet
    # than what is locked in a name (0.01 NMC).  There was a bug preventing
    # this from working.
    balance = self.nodes[1].getbalance ()
    keep = Decimal ("0.001")
    addr0 = self.nodes[0].getnewaddress ()
    self.nodes[1].sendtoaddress (addr0, balance - keep, "", "", True)
    addr1 = self.nodes[1].getnewaddress ()
    self.nodes[0].name_update ("node-1", "value", addr1)
    self.generate (0, 1)
    assert_equal (self.nodes[1].getbalance (), keep)
    self.nodes[1].name_update ("node-1", "new value")
    self.generate (0, 1)
    self.checkName (1, "node-1", "new value", None, False)
    assert self.nodes[1].getbalance () < Decimal ("0.01")

if __name__ == '__main__':
  NameRegistrationTest ().main ()
