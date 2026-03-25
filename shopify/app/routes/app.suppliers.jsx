import { useState, useCallback } from "react";
import {
  Page,
  Card,
  IndexTable,
  Badge,
  Button,
  Text,
  Modal,
  FormLayout,
  TextField,
  InlineStack,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }) => {
  await authenticate.admin(request);
  return null;
};

const initialSuppliers = [
  { id: "1", name: "TechSupply Co.", productCount: 24, fulfillmentTime: "3-5 days", active: true },
  { id: "2", name: "FitGear Wholesale", productCount: 18, fulfillmentTime: "2-4 days", active: true },
  { id: "3", name: "EcoGoods Ltd.", productCount: 31, fulfillmentTime: "4-7 days", active: true },
  { id: "4", name: "BrightTech Inc.", productCount: 12, fulfillmentTime: "3-6 days", active: false },
  { id: "5", name: "GreenSource Co.", productCount: 9, fulfillmentTime: "5-8 days", active: true },
];

const resourceName = { singular: "supplier", plural: "suppliers" };

const headings = [
  { title: "Name" },
  { title: "Products" },
  { title: "Fulfillment Time" },
  { title: "Status" },
];

const emptyForm = { name: "", apiEndpoint: "", apiKey: "", notes: "" };

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState(initialSuppliers);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const openModal = useCallback(() => {
    setForm(emptyForm);
    setModalOpen(true);
  }, []);

  const closeModal = useCallback(() => setModalOpen(false), []);

  const handleFieldChange = useCallback(
    (field) => (value) => setForm((prev) => ({ ...prev, [field]: value })),
    [],
  );

  const handleSave = useCallback(() => {
    if (!form.name.trim()) return;
    const newSupplier = {
      id: String(suppliers.length + 1),
      name: form.name,
      productCount: 0,
      fulfillmentTime: "TBD",
      active: true,
    };
    setSuppliers((prev) => [...prev, newSupplier]);
    closeModal();
  }, [form, suppliers.length, closeModal]);

  return (
    <Page
      title="Suppliers"
      primaryAction={<Button variant="primary" onClick={openModal}>Add Supplier</Button>}
    >
      <TitleBar title="Suppliers" />
      <Card padding="0">
        <IndexTable
          resourceName={resourceName}
          itemCount={suppliers.length}
          headings={headings}
          selectable={false}
        >
          {suppliers.map(({ id, name, productCount, fulfillmentTime, active }, index) => (
            <IndexTable.Row id={id} key={id} position={index}>
              <IndexTable.Cell>
                <Text variant="bodyMd" fontWeight="bold" as="span">{name}</Text>
              </IndexTable.Cell>
              <IndexTable.Cell>{productCount}</IndexTable.Cell>
              <IndexTable.Cell>{fulfillmentTime}</IndexTable.Cell>
              <IndexTable.Cell>
                <Badge tone={active ? "success" : "critical"}>
                  {active ? "Active" : "Inactive"}
                </Badge>
              </IndexTable.Cell>
            </IndexTable.Row>
          ))}
        </IndexTable>
      </Card>

      <Modal
        open={modalOpen}
        onClose={closeModal}
        title="Add Supplier"
        primaryAction={{ content: "Save", onAction: handleSave }}
        secondaryActions={[{ content: "Cancel", onAction: closeModal }]}
      >
        <Modal.Section>
          <FormLayout>
            <TextField
              label="Supplier Name"
              value={form.name}
              onChange={handleFieldChange("name")}
              autoComplete="off"
            />
            <TextField
              label="API Endpoint"
              value={form.apiEndpoint}
              onChange={handleFieldChange("apiEndpoint")}
              autoComplete="off"
              placeholder="https://api.supplier.com/v1"
            />
            <TextField
              label="API Key"
              value={form.apiKey}
              onChange={handleFieldChange("apiKey")}
              autoComplete="off"
              type="password"
            />
            <TextField
              label="Notes"
              value={form.notes}
              onChange={handleFieldChange("notes")}
              autoComplete="off"
              multiline={3}
            />
          </FormLayout>
        </Modal.Section>
      </Modal>
    </Page>
  );
}
