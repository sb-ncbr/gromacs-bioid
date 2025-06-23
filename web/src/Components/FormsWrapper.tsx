import { materialCategorizationTester, materialCells, materialRenderers } from '@jsonforms/material-renderers';
import { JsonForms, JsonFormsInitStateProps } from '@jsonforms/react';
import { JsonSchema, TesterContext, UISchemaElement } from '@jsonforms/core';
import { Skeleton, Stack, SvgIcon, Typography } from '@mui/material';
import MatrixRenderer from '../Renderers/MatrixRenderer'
import MatrixTester from '../Renderers/MatrixTester'
import MaterialCategorizationLayoutRenderer from '../Renderers/MaterialCategorizationLayout';
import { JSX } from 'react';
import { Code, Description, Home, Layers } from '@mui/icons-material';
import MaterialCategorizationLayoutTester from '../Renderers/MaterialCategorizationLayoutTester';

const renderers = [
  ...materialRenderers,
  { tester: MatrixTester, renderer: MatrixRenderer },
  { tester: MaterialCategorizationLayoutTester, renderer: MaterialCategorizationLayoutRenderer }
];

export const iconMap: { [key: string]: JSX.Element } = {
    'Administrative': <Home />,
    'Object': <SvgIcon><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><path d="M416 0c17.7 0 32 14.3 32 32c0 59.8-30.3 107.5-69.4 146.6c-28 28-62.5 53.5-97.3 77.4l-2.5 1.7c-11.9 8.1-23.8 16.1-35.5 23.9c0 0 0 0 0 0s0 0 0 0s0 0 0 0l-1.6 1c-6 4-11.9 7.9-17.8 11.9c-20.9 14-40.8 27.7-59.3 41.5l118.5 0c-9.8-7.4-20.1-14.7-30.7-22.1l7-4.7 3-2c15.1-10.1 30.9-20.6 46.7-31.6c25 18.1 48.9 37.3 69.4 57.7C417.7 372.5 448 420.2 448 480c0 17.7-14.3 32-32 32s-32-14.3-32-32L64 480c0 17.7-14.3 32-32 32s-32-14.3-32-32c0-59.8 30.3-107.5 69.4-146.6c28-28 62.5-53.5 97.3-77.4c-34.8-23.9-69.3-49.3-97.3-77.4C30.3 139.5 0 91.8 0 32C0 14.3 14.3 0 32 0S64 14.3 64 32l320 0c0-17.7 14.3-32 32-32zM338.6 384l-229.2 0c-10.1 10.6-18.6 21.3-25.5 32l280.2 0c-6.8-10.7-15.3-21.4-25.5-32zM109.4 128l229.2 0c10.1-10.7 18.6-21.3 25.5-32L83.9 96c6.8 10.7 15.3 21.3 25.5 32zm55.4 48c18.4 13.8 38.4 27.5 59.3 41.5c20.9-14 40.8-27.7 59.3-41.5l-118.5 0z"/></svg></SvgIcon>,
    'Simulation': <Description />,
    'System': <Layers />,
    'Software': <Code />,
    'administrative': <Home />,
    'simulated_object': <SvgIcon><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><path d="M416 0c17.7 0 32 14.3 32 32c0 59.8-30.3 107.5-69.4 146.6c-28 28-62.5 53.5-97.3 77.4l-2.5 1.7c-11.9 8.1-23.8 16.1-35.5 23.9c0 0 0 0 0 0s0 0 0 0s0 0 0 0l-1.6 1c-6 4-11.9 7.9-17.8 11.9c-20.9 14-40.8 27.7-59.3 41.5l118.5 0c-9.8-7.4-20.1-14.7-30.7-22.1l7-4.7 3-2c15.1-10.1 30.9-20.6 46.7-31.6c25 18.1 48.9 37.3 69.4 57.7C417.7 372.5 448 420.2 448 480c0 17.7-14.3 32-32 32s-32-14.3-32-32L64 480c0 17.7-14.3 32-32 32s-32-14.3-32-32c0-59.8 30.3-107.5 69.4-146.6c28-28 62.5-53.5 97.3-77.4c-34.8-23.9-69.3-49.3-97.3-77.4C30.3 139.5 0 91.8 0 32C0 14.3 14.3 0 32 0S64 14.3 64 32l320 0c0-17.7 14.3-32 32-32zM338.6 384l-229.2 0c-10.1 10.6-18.6 21.3-25.5 32l280.2 0c-6.8-10.7-15.3-21.4-25.5-32zM109.4 128l229.2 0c10.1-10.7 18.6-21.3 25.5-32L83.9 96c6.8 10.7 15.3 21.3 25.5 32zm55.4 48c18.4 13.8 38.4 27.5 59.3 41.5c20.9-14 40.8-27.7 59.3-41.5l-118.5 0z"/></svg></SvgIcon>,
    'simulation': <Description />,
    // 'software_information': <Code />,
    'system': <Layers />,
  };

  const labelMap: { [key: string]: string } = {
    'Administrative': 'Administrative',
    'Object': 'Object',
    'Simulation': 'Simulation',
    'System': 'System',
    'Software': 'Software',
    'administrative': 'Administrative',
    'simulated_object': 'Object',
    'simulation': 'Simulation',
    // 'software_information': 'Software',
    'system': 'System',
  };

export const IconLabel = ({label}: {label: string}) => {
  const text = labelMap[label] || label
  return (
    <Stack direction="row" spacing={1} alignItems="center">
      {iconMap[label]}
      <Typography variant="h3">{text}</Typography>
    </Stack>
  )
}


type FormsWrappedProps = {
  schema: Object,
  uischema: Object,
  data: any,
  setData: (data: any) => void,
  setErrors: (errors: any) => void
} & Omit<JsonFormsInitStateProps, "data" | "renderers" | "cells" | "schema" | "uischema" | "onChange">

const FormsWrapped = ({schema, uischema, data, setData, setErrors, ...other}: FormsWrappedProps): React.ReactElement => {

  return (
    <>
      <JsonForms
        schema={schema as JsonSchema}
        uischema={Object.keys(uischema).length > 0 ?  uischema as UISchemaElement : undefined}
        data={data}
        renderers={renderers}
        cells={materialCells}
        onChange={({ errors, data }) => {
          // XXX: Run extra validations here if needed
          setData(data)
          setErrors(errors)
        }}
        validationMode='NoValidation'
        {...other}
        />
    </>
  )
};

export const FormsWrapperSkeleton = () => {
  return (
    <Stack direction="column" spacing={1} justifyContent="space-evenly">
      <Skeleton variant="text" width="50%" height={50} />
      <Stack direction="row" spacing={1} justifyContent="space-evenly">
        <Skeleton variant="rectangular" width="50%" height={50} />
        <Skeleton variant="rectangular" width="50%" height={50} />
      </Stack>
    </Stack>
  )
}

export default FormsWrapped;
