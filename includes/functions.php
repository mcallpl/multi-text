<?php
require_once __DIR__ . '/db.php';

// ── SMS Sending ──

function sendSMS($phone, $carrier, $message, $contactId = null, $contactName = '') {
    global $CARRIER_GATEWAYS;

    if (!isset($CARRIER_GATEWAYS[$carrier])) {
        return ['success' => false, 'error' => 'Unknown carrier'];
    }

    $cleanPhone = preg_replace('/\D/', '', $phone);
    $gateway = $CARRIER_GATEWAYS[$carrier]['gateway'];
    $to = $cleanPhone . '@' . $gateway;

    $headers = "From: " . FROM_NAME . " <" . FROM_EMAIL . ">\r\n";
    $headers .= "MIME-Version: 1.0\r\n";
    $headers .= "Content-Type: text/plain; charset=UTF-8\r\n";

    $sent = @mail($to, '', $message, $headers);

    // Log to history
    $db = getDB();
    $status = $sent ? 'sent' : 'failed';
    $stmt = $db->prepare('INSERT INTO message_history (contact_id, contact_name, phone, carrier, message, status) VALUES (?, ?, ?, ?, ?, ?)');
    $stmt->bind_param('isssss', $contactId, $contactName, $phone, $carrier, $message, $status);
    $stmt->execute();
    $stmt->close();

    return ['success' => $sent];
}

function sendToGroup($groupId, $message) {
    $members = getGroupMembers($groupId);
    $results = [];
    foreach ($members as $contact) {
        $results[] = sendSMS($contact['phone'], $contact['carrier'], $message, $contact['id'], $contact['name']);
    }
    return $results;
}

// ── Contacts ──

function getContacts() {
    $db = getDB();
    $result = $db->query('SELECT * FROM contacts ORDER BY name');
    $rows = [];
    while ($row = $result->fetch_assoc()) {
        $rows[] = $row;
    }
    $result->free();
    return $rows;
}

function getContact($id) {
    $db = getDB();
    $stmt = $db->prepare('SELECT * FROM contacts WHERE id = ?');
    $stmt->bind_param('i', $id);
    $stmt->execute();
    $result = $stmt->get_result();
    $row = $result->fetch_assoc();
    $stmt->close();
    return $row;
}

function addContact($name, $phone, $carrier) {
    $db = getDB();
    $name = trim($name);
    $phone = trim($phone);
    $stmt = $db->prepare('INSERT INTO contacts (name, phone, carrier) VALUES (?, ?, ?)');
    $stmt->bind_param('sss', $name, $phone, $carrier);
    $ok = $stmt->execute();
    $stmt->close();
    return $ok;
}

function updateContact($id, $name, $phone, $carrier) {
    $db = getDB();
    $name = trim($name);
    $phone = trim($phone);
    $stmt = $db->prepare('UPDATE contacts SET name = ?, phone = ?, carrier = ? WHERE id = ?');
    $stmt->bind_param('sssi', $name, $phone, $carrier, $id);
    $ok = $stmt->execute();
    $stmt->close();
    return $ok;
}

function deleteContact($id) {
    $db = getDB();
    $stmt = $db->prepare('DELETE FROM contacts WHERE id = ?');
    $stmt->bind_param('i', $id);
    $ok = $stmt->execute();
    $stmt->close();
    return $ok;
}

// ── Groups ──

function getGroups() {
    $db = getDB();
    $result = $db->query('SELECT g.*, COUNT(gm.contact_id) AS member_count FROM groups_ g LEFT JOIN group_members gm ON g.id = gm.group_id GROUP BY g.id ORDER BY g.name');
    $rows = [];
    while ($row = $result->fetch_assoc()) {
        $rows[] = $row;
    }
    $result->free();
    return $rows;
}

function getGroup($id) {
    $db = getDB();
    $stmt = $db->prepare('SELECT * FROM groups_ WHERE id = ?');
    $stmt->bind_param('i', $id);
    $stmt->execute();
    $result = $stmt->get_result();
    $row = $result->fetch_assoc();
    $stmt->close();
    return $row;
}

function addGroup($name) {
    $db = getDB();
    $name = trim($name);
    $stmt = $db->prepare('INSERT INTO groups_ (name) VALUES (?)');
    $stmt->bind_param('s', $name);
    $ok = $stmt->execute();
    $stmt->close();
    return $ok;
}

function deleteGroup($id) {
    $db = getDB();
    $stmt = $db->prepare('DELETE FROM groups_ WHERE id = ?');
    $stmt->bind_param('i', $id);
    $ok = $stmt->execute();
    $stmt->close();
    return $ok;
}

function getGroupMembers($groupId) {
    $db = getDB();
    $stmt = $db->prepare('SELECT c.* FROM contacts c JOIN group_members gm ON c.id = gm.contact_id WHERE gm.group_id = ? ORDER BY c.name');
    $stmt->bind_param('i', $groupId);
    $stmt->execute();
    $result = $stmt->get_result();
    $rows = [];
    while ($row = $result->fetch_assoc()) {
        $rows[] = $row;
    }
    $stmt->close();
    return $rows;
}

function addGroupMember($groupId, $contactId) {
    $db = getDB();
    $stmt = $db->prepare('INSERT IGNORE INTO group_members (group_id, contact_id) VALUES (?, ?)');
    $stmt->bind_param('ii', $groupId, $contactId);
    $ok = $stmt->execute();
    $stmt->close();
    return $ok;
}

function removeGroupMember($groupId, $contactId) {
    $db = getDB();
    $stmt = $db->prepare('DELETE FROM group_members WHERE group_id = ? AND contact_id = ?');
    $stmt->bind_param('ii', $groupId, $contactId);
    $ok = $stmt->execute();
    $stmt->close();
    return $ok;
}

// ── Message History ──

function getMessageHistory($limit = 50) {
    $db = getDB();
    $stmt = $db->prepare('SELECT * FROM message_history ORDER BY sent_at DESC LIMIT ?');
    $stmt->bind_param('i', $limit);
    $stmt->execute();
    $result = $stmt->get_result();
    $rows = [];
    while ($row = $result->fetch_assoc()) {
        $rows[] = $row;
    }
    $stmt->close();
    return $rows;
}

function clearHistory() {
    $db = getDB();
    return $db->query('DELETE FROM message_history');
}
