# KubePMIx - architecture

## Motivation

## Role OpenPMIx in MPI jobs

## Architecture

KubePMIx instance encapsulates two servers in a single proces - OpenPMIx server (generated from openpmix python bindings) and a HTTP server which acts as a Mutating Admission Webhook Server for Kubernetes API. PMIx namespaces are created and env are injected.

User creates JobSet resource
Mutating Webhook intercepts the JobSet creation, creates namespace in the PMIx server and mutates the JobSet's PodSpec with namespace information
Mutating webhook intercepts the Pod creation and injects env vars.

## OpenPMIx built-in server features

## Dmodex parsing
